#!/usr/bin/env python3
"""Example: Socratic Workflow Builder

Demonstrates how to use the Socratic Agent Generation system to create
customized workflows through guided questioning.

This example shows:
1. Starting a session with a goal
2. Iterating through clarifying questions
3. Generating a workflow with agents
4. Evaluating success criteria

Usage:
    python examples/socratic_workflow_builder.py

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import json
from empathy_os.socratic import (
    SocraticWorkflowBuilder,
    Form,
    FormResponse,
)


def print_form(form: Form) -> None:
    """Pretty-print a form for console display."""
    print(f"\n{'=' * 60}")
    print(f"📋 {form.title}")
    print(f"{'=' * 60}")
    if form.description:
        print(f"\n{form.description}\n")

    print(f"Progress: {'▓' * int(form.progress * 20)}{'░' * (20 - int(form.progress * 20))} {form.progress:.0%}")
    print()

    for field in form.fields:
        required = "*" if field.validation.required else ""
        print(f"[{field.id}]{required} {field.label}")

        if field.help_text:
            print(f"   ℹ️  {field.help_text}")

        if field.options:
            for opt in field.options:
                rec = " (Recommended)" if opt.recommended else ""
                print(f"   • {opt.value}: {opt.label}{rec}")
                if opt.description:
                    print(f"     {opt.description}")
        print()


def simulate_user_answers(form: Form, round_num: int) -> dict:
    """Simulate user answers for demonstration."""
    # These would normally come from user input
    simulated_answers = {
        0: {  # Initial goal
            "goal": "I want to automate code reviews to catch security issues and improve code quality",
        },
        1: {  # First round
            "languages": ["python", "typescript"],
            "quality_focus": ["security", "maintainability"],
            "review_scope": "pr",
            "automation_level": "semi_auto",
            "team_size": "small",
        },
    }
    return simulated_answers.get(round_num, {})


def main():
    """Main example demonstrating Socratic workflow generation."""
    print("\n" + "=" * 60)
    print("🧠 SOCRATIC WORKFLOW BUILDER")
    print("   Generate optimized agent workflows through guided questioning")
    print("=" * 60)

    # Initialize the builder
    builder = SocraticWorkflowBuilder()

    # Start a new session
    print("\n📝 Starting new session...")
    session = builder.start_session()
    print(f"   Session ID: {session.session_id}")

    # Round 0: Get initial goal
    print("\n" + "-" * 60)
    print("ROUND 0: Goal Capture")
    print("-" * 60)

    initial_form = builder.get_initial_form()
    print_form(initial_form)

    # Simulate user providing a goal
    goal = "I want to automate code reviews to catch security issues and improve code quality"
    print(f"\n💬 User says: \"{goal}\"")

    # Set the goal (this triggers analysis)
    session = builder.set_goal(session, goal)

    # Show goal analysis results
    if session.goal_analysis:
        analysis = session.goal_analysis
        print(f"\n🔍 Goal Analysis:")
        print(f"   Domain: {analysis.domain}")
        print(f"   Intent: {analysis.intent}")
        print(f"   Confidence: {analysis.confidence:.0%}")
        print(f"   Keywords: {', '.join(analysis.keywords[:5])}")

        if analysis.ambiguities:
            print(f"\n   ⚠️  Ambiguities detected:")
            for amb in analysis.ambiguities:
                print(f"      - {amb}")

        if analysis.assumptions:
            print(f"\n   📌 Assumptions:")
            for assumption in analysis.assumptions:
                print(f"      - {assumption}")

    # Round 1: Clarifying questions
    print("\n" + "-" * 60)
    print("ROUND 1: Clarifying Questions")
    print("-" * 60)

    questions_form = builder.get_next_questions(session)
    if questions_form:
        print_form(questions_form)

        # Simulate user answers
        answers = simulate_user_answers(questions_form, 1)
        print("\n💬 User answers:")
        for key, value in answers.items():
            print(f"   {key}: {value}")

        session = builder.submit_answers(session, answers)

    # Check if ready to generate
    print("\n" + "-" * 60)
    print("SESSION STATUS")
    print("-" * 60)

    summary = builder.get_session_summary(session)
    print(f"\n📊 Session Summary:")
    print(f"   State: {summary['state']}")
    print(f"   Domain: {summary['domain']}")
    print(f"   Confidence: {summary['confidence']:.0%}")
    print(f"   Requirements Completeness: {summary['requirements_completeness']:.0%}")
    print(f"   Ready to Generate: {'✅ Yes' if summary['ready_to_generate'] else '❌ No'}")

    # Check if more questions needed
    next_form = builder.get_next_questions(session)
    if next_form and not builder.is_ready_to_generate(session):
        print("\n⚠️  More questions needed...")
        print_form(next_form)

    # Generate workflow
    if builder.is_ready_to_generate(session):
        print("\n" + "=" * 60)
        print("🚀 GENERATING WORKFLOW")
        print("=" * 60)

        workflow = builder.generate_workflow(session)

        print(f"\n{workflow.describe()}")

        # Show blueprint details
        blueprint = session.blueprint
        if blueprint:
            print(f"\n📋 Blueprint Details:")
            print(f"   Name: {blueprint.name}")
            print(f"   Domain: {blueprint.domain}")
            print(f"   Languages: {', '.join(blueprint.supported_languages)}")
            print(f"   Quality Focus: {', '.join(blueprint.quality_focus)}")
            print(f"   Automation: {blueprint.automation_level}")

            # Show success criteria
            if blueprint.success_criteria:
                criteria = blueprint.success_criteria
                print(f"\n📊 Success Criteria:")
                print(f"   Name: {criteria.name}")
                print(f"   Threshold: {criteria.success_threshold:.0%}")
                print(f"   Metrics:")
                for metric in criteria.metrics:
                    primary = " (Primary)" if metric.is_primary else ""
                    print(f"     - {metric.name}: {metric.metric_type.value}{primary}")

        # Show serialized blueprint (for persistence)
        print("\n📦 Serialized Blueprint (JSON):")
        print("-" * 40)
        if blueprint:
            blueprint_json = json.dumps(blueprint.to_dict(), indent=2, default=str)
            # Show first 50 lines
            lines = blueprint_json.split("\n")[:50]
            print("\n".join(lines))
            if len(blueprint_json.split("\n")) > 50:
                print("... (truncated)")

    print("\n" + "=" * 60)
    print("✅ Example Complete!")
    print("=" * 60)


def interactive_demo():
    """Interactive demonstration with actual user input."""
    print("\n" + "=" * 60)
    print("🧠 INTERACTIVE SOCRATIC WORKFLOW BUILDER")
    print("=" * 60)

    builder = SocraticWorkflowBuilder()
    session = builder.start_session()

    # Get goal from user
    print("\n📝 What would you like to accomplish?")
    print("   (Describe your goal in your own words)")
    print()

    goal = input("Your goal: ").strip()
    if not goal:
        goal = "I want to automate code reviews"
        print(f"   Using default: \"{goal}\"")

    session = builder.set_goal(session, goal)

    # Show analysis
    if session.goal_analysis:
        print(f"\n🔍 I understand you want: {session.goal_analysis.intent}")
        print(f"   Domain: {session.goal_analysis.domain}")
        print(f"   Confidence: {session.goal_analysis.confidence:.0%}")

    # Iterate through questions
    while not builder.is_ready_to_generate(session):
        form = builder.get_next_questions(session)
        if not form:
            break

        print_form(form)

        # Collect answers
        answers = {}
        for field in form.fields:
            if field.options:
                print(f"\n{field.label}")
                for i, opt in enumerate(field.options, 1):
                    print(f"  {i}. {opt.label}")

                response = input("Enter number(s) separated by comma: ").strip()
                if response:
                    indices = [int(x.strip()) - 1 for x in response.split(",") if x.strip().isdigit()]
                    selected = [field.options[i].value for i in indices if 0 <= i < len(field.options)]
                    answers[field.id] = selected if len(selected) > 1 else selected[0] if selected else None
            else:
                response = input(f"{field.label}: ").strip()
                if response:
                    answers[field.id] = response

        if answers:
            session = builder.submit_answers(session, answers)

    # Generate
    if builder.is_ready_to_generate(session):
        print("\n🚀 Generating your workflow...")
        workflow = builder.generate_workflow(session)
        print(f"\n{workflow.describe()}")

    print("\n✅ Done!")


if __name__ == "__main__":
    import sys

    if "--interactive" in sys.argv:
        interactive_demo()
    else:
        main()
