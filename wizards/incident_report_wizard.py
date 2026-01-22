"""
Incident Report Wizard Router - AI Nurse Florence
Following Wizard Pattern Implementation

Structured safety event documentation for incident/variance reporting.
HIPAA-compliant, objective language, based on patient safety best practices.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from src.services import get_service
from src.utils.api_responses import create_success_response
from src.utils.config import get_settings

logger = logging.getLogger(__name__)

try:
    from src.services.translation_service import translate_text

    _has_translation = True
except ImportError:
    _has_translation = False

    async def translate_text(
        text: str,
        target_language: str,
        source_language: str = "en",
        context: str = "medical",
    ):
        return {"translated_text": text, "success": False}


settings = get_settings()

router = APIRouter(
    prefix="/wizards/incident-report",
    tags=["clinical-wizards"],
    responses={
        404: {"description": "Wizard session not found"},
        422: {"description": "Invalid wizard step data"},
        500: {"description": "Wizard processing error"},
    },
)

try:
    from src.utils.redis_cache import get_redis_client

    _has_redis = True
except ImportError:
    _has_redis = False

_wizard_sessions: dict[str, dict[str, Any]] = {}

INCIDENT_REPORT_STEPS = {
    1: {
        "step": 1,
        "title": "Incident Overview",
        "prompt": "Document basic incident information",
        "fields": [
            "incident_date_time",
            "incident_location",
            "incident_type",
            "patient_involved",
            "reporter_name",
            "reporter_role",
        ],
        "help_text": "Record when and where the incident occurred, type of incident, and reporting information",
    },
    2: {
        "step": 2,
        "title": "Incident Description",
        "prompt": "Describe what happened in objective, factual terms",
        "fields": [
            "incident_description",
            "sequence_of_events",
            "witnesses",
            "patient_condition_before",
            "patient_condition_after",
            "immediate_actions_taken",
        ],
        "help_text": "Use objective language. Describe facts, not opinions or blame. Include timeline and witnesses.",
    },
    3: {
        "step": 3,
        "title": "Contributing Factors",
        "prompt": "Identify potential contributing factors",
        "fields": [
            "environmental_factors",
            "equipment_involved",
            "staffing_factors",
            "communication_issues",
            "policy_procedure_gaps",
            "other_factors",
        ],
        "help_text": "Note environmental, equipment, staffing, or system factors. Focus on improvement, not blame.",
    },
    4: {
        "step": 4,
        "title": "Response & Follow-up",
        "prompt": "Document response actions and follow-up",
        "fields": [
            "notifications_made",
            "medical_response",
            "family_notification",
            "documentation_completed",
            "follow_up_required",
            "prevention_recommendations",
        ],
        "help_text": "Who was notified, what medical response occurred, family communication, and recommendations for prevention",
    },
    5: {
        "step": 5,
        "title": "Review & Finalize",
        "prompt": "Review your incident report and finalize the document",
        "fields": ["review_complete", "user_approved"],
        "help_text": "Review all sections of the incident report. Click 'Generate Preview' to see the formatted document. You can go back to edit any section before finalizing.",
        "is_review_step": True,
    },
}

EDU_BANNER = """
⚠️ INCIDENT REPORTING NOTICE ⚠️
This incident report wizard is for educational and quality improvement purposes.
Incident reports are confidential peer review documents. Use objective,
non-judgmental language. Focus on facts and system improvement, not individual blame.
"""


async def _store_wizard_session(wizard_id: str, session_data: dict[str, Any]) -> bool:
    try:
        if _has_redis:
            import json

            redis_client = await get_redis_client()
            if redis_client:
                await redis_client.setex(
                    f"wizard:incident_report:{wizard_id}",
                    7200,
                    json.dumps(session_data),  # FIXED: use JSON
                )
                return True
    except Exception:  # noqa: BLE001
        # INTENTIONAL: Graceful degradation - fall back to in-memory storage if Redis fails
        pass
    _wizard_sessions[wizard_id] = session_data
    return True


async def _get_wizard_session(wizard_id: str) -> dict[str, Any] | None:
    try:
        if _has_redis:
            import json

            redis_client = await get_redis_client()
            if redis_client:
                session_str = await redis_client.get(f"wizard:incident_report:{wizard_id}")
                if session_str:
                    # SECURITY FIX: Use json.loads() instead of ast.literal_eval()
                    return json.loads(session_str)
    except Exception:  # noqa: BLE001
        # INTENTIONAL: Graceful degradation - fall back to in-memory storage if Redis fails
        pass
    return _wizard_sessions.get(wizard_id)


def _get_step_data(step: int) -> dict[str, Any]:
    if step not in INCIDENT_REPORT_STEPS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid step: {step}")
    step_config = INCIDENT_REPORT_STEPS[step]
    return {
        "step": step,
        "title": step_config["title"],
        "prompt": step_config["prompt"],
        "fields": step_config["fields"],
        "help_text": step_config["help_text"],
    }


def _generate_incident_report(collected_data: dict[str, Any]) -> dict[str, Any]:
    narrative = f"""
INCIDENT REPORT - CONFIDENTIAL QUALITY IMPROVEMENT DOCUMENT

INCIDENT INFORMATION
Date/Time of Incident: {collected_data.get('incident_date_time', 'Not documented')}
Location: {collected_data.get('incident_location', 'Not documented')}
Type of Incident: {collected_data.get('incident_type', 'Not documented')}
Patient Involved: {collected_data.get('patient_involved', 'Not applicable')}
Reported By: {collected_data.get('reporter_name', 'Not documented')} ({collected_data.get('reporter_role', 'Not documented')})

INCIDENT DESCRIPTION (Objective, Factual Account)
Description: {collected_data.get('incident_description', 'Not documented')}

Sequence of Events: {collected_data.get('sequence_of_events', 'Not documented')}

Witnesses: {collected_data.get('witnesses', 'None identified')}

Patient Condition Before Incident: {collected_data.get('patient_condition_before', 'Not applicable')}

Patient Condition After Incident: {collected_data.get('patient_condition_after', 'Not applicable')}

Immediate Actions Taken: {collected_data.get('immediate_actions_taken', 'Not documented')}

CONTRIBUTING FACTORS
Environmental Factors: {collected_data.get('environmental_factors', 'None identified')}
Equipment Involved: {collected_data.get('equipment_involved', 'None')}
Staffing Factors: {collected_data.get('staffing_factors', 'None identified')}
Communication Issues: {collected_data.get('communication_issues', 'None identified')}
Policy/Procedure Gaps: {collected_data.get('policy_procedure_gaps', 'None identified')}
Other Contributing Factors: {collected_data.get('other_factors', 'None identified')}

RESPONSE & FOLLOW-UP
Notifications Made: {collected_data.get('notifications_made', 'Not documented')}
Medical Response: {collected_data.get('medical_response', 'Not applicable')}
Family Notification: {collected_data.get('family_notification', 'Not applicable')}
Documentation Completed: {collected_data.get('documentation_completed', 'Medical record updated')}
Follow-up Required: {collected_data.get('follow_up_required', 'Not documented')}

RECOMMENDATIONS FOR PREVENTION
{collected_data.get('prevention_recommendations', 'Not documented')}

Report Submitted: {datetime.now().strftime('%Y-%m-%d %H:%M')}

This report is a confidential quality improvement document protected under peer review statutes.
Use for quality improvement and risk management purposes only.
"""
    return {
        "incident_report": collected_data,
        "narrative": narrative.strip(),
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "wizard_type": "incident_report",
        },
        "banner": EDU_BANNER,
    }


@router.post("/start", summary="Start Incident Report Wizard")
async def start_incident_report_wizard():
    try:
        wizard_id = str(uuid4())
        session_data = {
            "wizard_id": wizard_id,
            "wizard_type": "incident_report",
            "current_step": 1,
            "total_steps": 5,
            "collected_data": {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        await _store_wizard_session(wizard_id, session_data)
        step_data = _get_step_data(1)
        response_data = {
            "wizard_session": session_data,
            "current_step": step_data,
            "progress": {"current": 1, "total": 4, "percentage": 25},
            "banner": EDU_BANNER,
        }
        return create_success_response(
            data=response_data, message="Incident report wizard started successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{wizard_id}/step", summary="Submit incident report step")
async def submit_incident_report_step(wizard_id: str, step_data: dict[str, Any]):
    try:
        session = await _get_wizard_session(wizard_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        current_step = session["current_step"]
        session["collected_data"].update(step_data.get("data", {}))
        session["updated_at"] = datetime.now().isoformat()

        # Advance to next step (but don't auto-complete, even on final step)
        if current_step < session["total_steps"]:
            next_step = current_step + 1
            session["current_step"] = next_step
        else:
            # On review step - stay on same step, don't auto-complete
            next_step = current_step

        await _store_wizard_session(wizard_id, session)
        return create_success_response(
            data={
                "wizard_session": session,
                "current_step": _get_step_data(next_step),
                "progress": {
                    "current": next_step,
                    "total": session["total_steps"],
                    "percentage": int((next_step / session["total_steps"]) * 100),
                },
            },
            message=f"Step {current_step} completed",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{wizard_id}/preview", summary="Preview incident report")
async def preview_incident_report(wizard_id: str):
    """
    Generate preview of incident report without finalizing.

    This endpoint allows users to see the formatted incident report before
    finalizing it. The report is NOT marked as complete. Users can
    still go back and edit data after previewing.
    """
    try:
        session = await _get_wizard_session(wizard_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        # Verify user is on review step
        if session["current_step"] != session["total_steps"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not on review step. Complete steps 1-{session['total_steps']-1} first.",
            )

        # Generate preview report (does NOT mark as complete)
        preview_report = _generate_incident_report(session["collected_data"])

        # Store preview in session
        session["preview_report"] = preview_report
        session["preview_generated_at"] = datetime.now().isoformat()
        await _store_wizard_session(wizard_id, session)

        response_data = {
            "preview": preview_report,
            "wizard_session": session,
            "message": "Review the incident report above. Click 'Finalize Report' to save, or go back to edit any section.",
        }

        return create_success_response(data=response_data, message="Preview generated successfully")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{wizard_id}/save", summary="Finalize incident report")
async def save_incident_report(wizard_id: str, approval_data: dict[str, Any]):
    """
    Finalize and save the incident report after user review and approval.

    Requires that the user has:
    1. Generated a preview first (/preview endpoint)
    2. Explicitly approved the report (user_approved: true)

    Only after calling this endpoint is the report marked as complete.
    """
    try:
        session = await _get_wizard_session(wizard_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        # Verify preview was generated
        if "preview_report" not in session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must generate preview before saving. Call /preview endpoint first.",
            )

        # Verify user explicitly approved
        if not approval_data.get("user_approved", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User approval required. Set 'user_approved': true in request body.",
            )

        # NOW we mark as complete
        session["completed"] = True
        session["completed_at"] = datetime.now().isoformat()
        session["final_report"] = session["preview_report"]
        session["user_approved"] = True

        await _store_wizard_session(wizard_id, session)

        response_data = {
            "wizard_session": session,
            "report": session["final_report"],
            "completed": True,
        }

        return create_success_response(
            data=response_data, message="Incident report finalized successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{wizard_id}/enhance", summary="Enhance incident report text")
async def enhance_incident_report_text(wizard_id: str, text_data: dict[str, Any]):
    try:
        session = await _get_wizard_session(wizard_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        original_text = text_data.get("text", "")
        field_name = text_data.get("field", "text")
        if not original_text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No text provided",
            )
        chat_service = get_service("chat")
        enhancement_prompt = f"Enhance this incident report field ({field_name}) using objective, non-judgmental language. Focus on facts, not blame: {original_text}"
        chat_response = await chat_service.chat(
            message=enhancement_prompt,
            conversation_id=f"incident_enhance_{wizard_id}",
            context={"wizard_id": wizard_id, "field": field_name},
        )
        enhanced_text = chat_response.get("response", original_text)
        return create_success_response(
            data={
                "original_text": original_text,
                "enhanced_text": enhanced_text,
                "field": field_name,
            },
            message="Text enhanced successfully",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{wizard_id}/report", summary="Get incident report")
async def get_incident_report(wizard_id: str):
    try:
        session = await _get_wizard_session(wizard_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if not session.get("completed", False):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Wizard not completed",
            )
        report = _generate_incident_report(session["collected_data"])
        return create_success_response(
            data={"wizard_session": session, "report": report},
            message="Report retrieved successfully",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


__all__ = ["router"]
