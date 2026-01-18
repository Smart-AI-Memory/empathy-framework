"""Collaboration Features for Socratic Workflow Builder

Enables multiple users to collaboratively refine workflow requirements
and review generated workflows.

Features:
- Collaborative sessions with multiple participants
- Comment and discussion threads
- Voting on requirements and decisions
- Change tracking and history
- Conflict resolution
- Real-time synchronization support

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable


# =============================================================================
# DATA STRUCTURES
# =============================================================================


class ParticipantRole(Enum):
    """Roles for session participants."""

    OWNER = "owner"  # Full control
    EDITOR = "editor"  # Can edit and vote
    REVIEWER = "reviewer"  # Can comment and vote
    VIEWER = "viewer"  # Read-only access


class CommentStatus(Enum):
    """Status of a comment."""

    OPEN = "open"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"


class VoteType(Enum):
    """Types of votes."""

    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


class ChangeType(Enum):
    """Types of changes tracked."""

    GOAL_SET = "goal_set"
    ANSWER_SUBMITTED = "answer_submitted"
    REQUIREMENT_ADDED = "requirement_added"
    REQUIREMENT_REMOVED = "requirement_removed"
    AGENT_ADDED = "agent_added"
    AGENT_REMOVED = "agent_removed"
    WORKFLOW_MODIFIED = "workflow_modified"
    COMMENT_ADDED = "comment_added"
    VOTE_CAST = "vote_cast"


@dataclass
class Participant:
    """A participant in a collaborative session."""

    user_id: str
    name: str
    email: str | None = None
    role: ParticipantRole = ParticipantRole.VIEWER
    joined_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    is_online: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "role": self.role.value,
            "joined_at": self.joined_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "is_online": self.is_online,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Participant:
        return cls(
            user_id=data["user_id"],
            name=data["name"],
            email=data.get("email"),
            role=ParticipantRole(data.get("role", "viewer")),
            joined_at=datetime.fromisoformat(data["joined_at"]),
            last_active=datetime.fromisoformat(data["last_active"]),
            is_online=data.get("is_online", False),
        )


@dataclass
class Comment:
    """A comment on a session or specific element."""

    comment_id: str
    author_id: str
    content: str
    target_type: str  # "session", "answer", "agent", "stage", etc.
    target_id: str  # ID of the target element
    status: CommentStatus = CommentStatus.OPEN
    parent_id: str | None = None  # For threaded comments
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    reactions: dict[str, list[str]] = field(default_factory=dict)  # emoji -> user_ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "author_id": self.author_id,
            "content": self.content,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "status": self.status.value,
            "parent_id": self.parent_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "reactions": self.reactions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Comment:
        return cls(
            comment_id=data["comment_id"],
            author_id=data["author_id"],
            content=data["content"],
            target_type=data["target_type"],
            target_id=data["target_id"],
            status=CommentStatus(data.get("status", "open")),
            parent_id=data.get("parent_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            reactions=data.get("reactions", {}),
        )


@dataclass
class Vote:
    """A vote on a decision or requirement."""

    vote_id: str
    voter_id: str
    target_type: str  # "requirement", "agent", "workflow", etc.
    target_id: str
    vote_type: VoteType
    comment: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "vote_id": self.vote_id,
            "voter_id": self.voter_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "vote_type": self.vote_type.value,
            "comment": self.comment,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Vote:
        return cls(
            vote_id=data["vote_id"],
            voter_id=data["voter_id"],
            target_type=data["target_type"],
            target_id=data["target_id"],
            vote_type=VoteType(data["vote_type"]),
            comment=data.get("comment", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class Change:
    """A tracked change in the session."""

    change_id: str
    change_type: ChangeType
    author_id: str
    description: str
    before_value: Any = None
    after_value: Any = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_id": self.change_id,
            "change_type": self.change_type.value,
            "author_id": self.author_id,
            "description": self.description,
            "before_value": self.before_value,
            "after_value": self.after_value,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Change:
        return cls(
            change_id=data["change_id"],
            change_type=ChangeType(data["change_type"]),
            author_id=data["author_id"],
            description=data["description"],
            before_value=data.get("before_value"),
            after_value=data.get("after_value"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class VotingResult:
    """Result of a voting round."""

    target_id: str
    total_votes: int
    approvals: int
    rejections: int
    abstentions: int
    is_approved: bool
    quorum_reached: bool

    @property
    def approval_rate(self) -> float:
        """Calculate approval rate (excluding abstentions)."""
        active_votes = self.approvals + self.rejections
        if active_votes == 0:
            return 0.0
        return self.approvals / active_votes


# =============================================================================
# COLLABORATIVE SESSION
# =============================================================================


@dataclass
class CollaborativeSession:
    """A session with collaboration features enabled."""

    session_id: str
    base_session_id: str  # ID of the underlying SocraticSession
    name: str
    description: str = ""
    participants: list[Participant] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)
    votes: list[Vote] = field(default_factory=list)
    changes: list[Change] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    require_approval: bool = True
    approval_threshold: float = 0.5  # 50% approval required
    quorum: float = 0.5  # 50% participation required

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "base_session_id": self.base_session_id,
            "name": self.name,
            "description": self.description,
            "participants": [p.to_dict() for p in self.participants],
            "comments": [c.to_dict() for c in self.comments],
            "votes": [v.to_dict() for v in self.votes],
            "changes": [c.to_dict() for c in self.changes],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "require_approval": self.require_approval,
            "approval_threshold": self.approval_threshold,
            "quorum": self.quorum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollaborativeSession:
        return cls(
            session_id=data["session_id"],
            base_session_id=data["base_session_id"],
            name=data["name"],
            description=data.get("description", ""),
            participants=[Participant.from_dict(p) for p in data.get("participants", [])],
            comments=[Comment.from_dict(c) for c in data.get("comments", [])],
            votes=[Vote.from_dict(v) for v in data.get("votes", [])],
            changes=[Change.from_dict(c) for c in data.get("changes", [])],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            require_approval=data.get("require_approval", True),
            approval_threshold=data.get("approval_threshold", 0.5),
            quorum=data.get("quorum", 0.5),
        )


# =============================================================================
# COLLABORATION MANAGER
# =============================================================================


class CollaborationManager:
    """Manages collaborative workflow sessions."""

    def __init__(self, storage_path: Path | str | None = None):
        """Initialize the manager.

        Args:
            storage_path: Path to persist collaboration data
        """
        if storage_path is None:
            storage_path = Path.home() / ".empathy" / "socratic" / "collaboration"
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._sessions: dict[str, CollaborativeSession] = {}
        self._change_listeners: list[Callable[[Change], None]] = []

        self._load_sessions()

    def create_session(
        self,
        base_session_id: str,
        name: str,
        owner_id: str,
        owner_name: str,
        description: str = "",
    ) -> CollaborativeSession:
        """Create a new collaborative session.

        Args:
            base_session_id: ID of the underlying SocraticSession
            name: Session name
            owner_id: ID of the session owner
            owner_name: Name of the session owner
            description: Optional description

        Returns:
            The created session
        """
        session_id = hashlib.sha256(
            f"{base_session_id}:{time.time()}".encode()
        ).hexdigest()[:12]

        owner = Participant(
            user_id=owner_id,
            name=owner_name,
            role=ParticipantRole.OWNER,
            is_online=True,
        )

        session = CollaborativeSession(
            session_id=session_id,
            base_session_id=base_session_id,
            name=name,
            description=description,
            participants=[owner],
        )

        self._sessions[session_id] = session
        self._save_session(session)

        return session

    def get_session(self, session_id: str) -> CollaborativeSession | None:
        """Get a collaborative session by ID."""
        return self._sessions.get(session_id)

    def add_participant(
        self,
        session_id: str,
        user_id: str,
        name: str,
        email: str | None = None,
        role: ParticipantRole = ParticipantRole.REVIEWER,
    ) -> Participant | None:
        """Add a participant to a session.

        Args:
            session_id: Session ID
            user_id: User ID
            name: User name
            email: Optional email
            role: Participant role

        Returns:
            The added participant or None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        # Check if already a participant
        existing = next((p for p in session.participants if p.user_id == user_id), None)
        if existing:
            return existing

        participant = Participant(
            user_id=user_id,
            name=name,
            email=email,
            role=role,
        )
        session.participants.append(participant)
        session.updated_at = datetime.now()

        self._save_session(session)
        return participant

    def update_participant_role(
        self,
        session_id: str,
        user_id: str,
        new_role: ParticipantRole,
        by_user_id: str,
    ) -> bool:
        """Update a participant's role.

        Args:
            session_id: Session ID
            user_id: User ID to update
            new_role: New role
            by_user_id: ID of user making the change

        Returns:
            True if successful
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        # Check permissions
        requester = next((p for p in session.participants if p.user_id == by_user_id), None)
        if not requester or requester.role != ParticipantRole.OWNER:
            return False

        participant = next((p for p in session.participants if p.user_id == user_id), None)
        if not participant:
            return False

        participant.role = new_role
        session.updated_at = datetime.now()

        self._save_session(session)
        return True

    def add_comment(
        self,
        session_id: str,
        author_id: str,
        content: str,
        target_type: str,
        target_id: str,
        parent_id: str | None = None,
    ) -> Comment | None:
        """Add a comment to a session.

        Args:
            session_id: Session ID
            author_id: Comment author ID
            content: Comment content
            target_type: Type of target element
            target_id: ID of target element
            parent_id: Optional parent comment ID for threading

        Returns:
            The created comment or None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        # Verify author is a participant
        author = next((p for p in session.participants if p.user_id == author_id), None)
        if not author:
            return None

        comment_id = hashlib.sha256(
            f"{session_id}:{author_id}:{time.time()}".encode()
        ).hexdigest()[:12]

        comment = Comment(
            comment_id=comment_id,
            author_id=author_id,
            content=content,
            target_type=target_type,
            target_id=target_id,
            parent_id=parent_id,
        )
        session.comments.append(comment)
        session.updated_at = datetime.now()

        # Track change
        self._track_change(
            session,
            ChangeType.COMMENT_ADDED,
            author_id,
            f"Comment added on {target_type}",
            after_value={"comment_id": comment_id, "target": target_id},
        )

        self._save_session(session)
        return comment

    def resolve_comment(
        self,
        session_id: str,
        comment_id: str,
        by_user_id: str,
        status: CommentStatus = CommentStatus.RESOLVED,
    ) -> bool:
        """Resolve a comment.

        Args:
            session_id: Session ID
            comment_id: Comment ID
            by_user_id: User resolving the comment
            status: New status

        Returns:
            True if successful
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        comment = next((c for c in session.comments if c.comment_id == comment_id), None)
        if not comment:
            return False

        comment.status = status
        comment.updated_at = datetime.now()
        session.updated_at = datetime.now()

        self._save_session(session)
        return True

    def add_reaction(
        self,
        session_id: str,
        comment_id: str,
        user_id: str,
        emoji: str,
    ) -> bool:
        """Add a reaction to a comment.

        Args:
            session_id: Session ID
            comment_id: Comment ID
            user_id: User adding reaction
            emoji: Emoji reaction

        Returns:
            True if successful
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        comment = next((c for c in session.comments if c.comment_id == comment_id), None)
        if not comment:
            return False

        if emoji not in comment.reactions:
            comment.reactions[emoji] = []

        if user_id not in comment.reactions[emoji]:
            comment.reactions[emoji].append(user_id)
            session.updated_at = datetime.now()
            self._save_session(session)

        return True

    def cast_vote(
        self,
        session_id: str,
        voter_id: str,
        target_type: str,
        target_id: str,
        vote_type: VoteType,
        comment: str = "",
    ) -> Vote | None:
        """Cast a vote on a target.

        Args:
            session_id: Session ID
            voter_id: Voter ID
            target_type: Type of target
            target_id: ID of target
            vote_type: Type of vote
            comment: Optional comment

        Returns:
            The cast vote or None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        # Verify voter is a participant with voting rights
        voter = next((p for p in session.participants if p.user_id == voter_id), None)
        if not voter or voter.role == ParticipantRole.VIEWER:
            return None

        # Check if already voted
        existing = next(
            (v for v in session.votes
             if v.voter_id == voter_id and v.target_type == target_type and v.target_id == target_id),
            None
        )
        if existing:
            # Update existing vote
            existing.vote_type = vote_type
            existing.comment = comment
            existing.created_at = datetime.now()
            session.updated_at = datetime.now()
            self._save_session(session)
            return existing

        vote_id = hashlib.sha256(
            f"{session_id}:{voter_id}:{target_id}:{time.time()}".encode()
        ).hexdigest()[:12]

        vote = Vote(
            vote_id=vote_id,
            voter_id=voter_id,
            target_type=target_type,
            target_id=target_id,
            vote_type=vote_type,
            comment=comment,
        )
        session.votes.append(vote)
        session.updated_at = datetime.now()

        # Track change
        self._track_change(
            session,
            ChangeType.VOTE_CAST,
            voter_id,
            f"{vote_type.value} vote on {target_type}",
            after_value={"target": target_id, "vote": vote_type.value},
        )

        self._save_session(session)
        return vote

    def get_voting_result(
        self,
        session_id: str,
        target_type: str,
        target_id: str,
    ) -> VotingResult | None:
        """Get voting results for a target.

        Args:
            session_id: Session ID
            target_type: Type of target
            target_id: ID of target

        Returns:
            VotingResult or None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        # Get votes for this target
        votes = [
            v for v in session.votes
            if v.target_type == target_type and v.target_id == target_id
        ]

        # Count by type
        approvals = sum(1 for v in votes if v.vote_type == VoteType.APPROVE)
        rejections = sum(1 for v in votes if v.vote_type == VoteType.REJECT)
        abstentions = sum(1 for v in votes if v.vote_type == VoteType.ABSTAIN)

        # Calculate quorum
        eligible_voters = [
            p for p in session.participants
            if p.role != ParticipantRole.VIEWER
        ]
        participation_rate = len(votes) / len(eligible_voters) if eligible_voters else 0
        quorum_reached = participation_rate >= session.quorum

        # Calculate approval
        active_votes = approvals + rejections
        approval_rate = approvals / active_votes if active_votes > 0 else 0
        is_approved = quorum_reached and approval_rate >= session.approval_threshold

        return VotingResult(
            target_id=target_id,
            total_votes=len(votes),
            approvals=approvals,
            rejections=rejections,
            abstentions=abstentions,
            is_approved=is_approved,
            quorum_reached=quorum_reached,
        )

    def get_comments_for_target(
        self,
        session_id: str,
        target_type: str,
        target_id: str,
        include_resolved: bool = True,
    ) -> list[Comment]:
        """Get comments for a target.

        Args:
            session_id: Session ID
            target_type: Type of target
            target_id: ID of target
            include_resolved: Include resolved comments

        Returns:
            List of comments
        """
        session = self._sessions.get(session_id)
        if not session:
            return []

        comments = [
            c for c in session.comments
            if c.target_type == target_type and c.target_id == target_id
        ]

        if not include_resolved:
            comments = [c for c in comments if c.status == CommentStatus.OPEN]

        return sorted(comments, key=lambda c: c.created_at)

    def get_change_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[Change]:
        """Get change history for a session.

        Args:
            session_id: Session ID
            limit: Maximum changes to return

        Returns:
            List of changes (most recent first)
        """
        session = self._sessions.get(session_id)
        if not session:
            return []

        return sorted(
            session.changes,
            key=lambda c: c.created_at,
            reverse=True,
        )[:limit]

    def track_change(
        self,
        session_id: str,
        change_type: ChangeType,
        author_id: str,
        description: str,
        before_value: Any = None,
        after_value: Any = None,
    ):
        """Track a change in the session.

        Args:
            session_id: Session ID
            change_type: Type of change
            author_id: Author of the change
            description: Description of the change
            before_value: Value before change
            after_value: Value after change
        """
        session = self._sessions.get(session_id)
        if session:
            self._track_change(
                session, change_type, author_id, description,
                before_value, after_value
            )
            self._save_session(session)

    def add_change_listener(self, listener: Callable[[Change], None]):
        """Add a listener for changes.

        Args:
            listener: Callback function
        """
        self._change_listeners.append(listener)

    def remove_change_listener(self, listener: Callable[[Change], None]):
        """Remove a change listener.

        Args:
            listener: Callback function to remove
        """
        if listener in self._change_listeners:
            self._change_listeners.remove(listener)

    def _track_change(
        self,
        session: CollaborativeSession,
        change_type: ChangeType,
        author_id: str,
        description: str,
        before_value: Any = None,
        after_value: Any = None,
    ):
        """Internal method to track a change."""
        change_id = hashlib.sha256(
            f"{session.session_id}:{time.time()}".encode()
        ).hexdigest()[:12]

        change = Change(
            change_id=change_id,
            change_type=change_type,
            author_id=author_id,
            description=description,
            before_value=before_value,
            after_value=after_value,
        )
        session.changes.append(change)

        # Notify listeners
        for listener in self._change_listeners:
            try:
                listener(change)
            except Exception:
                pass

    def _save_session(self, session: CollaborativeSession):
        """Save a session to storage."""
        path = self.storage_path / f"{session.session_id}.json"
        with path.open("w") as f:
            json.dump(session.to_dict(), f, indent=2)

    def _load_sessions(self):
        """Load all sessions from storage."""
        for path in self.storage_path.glob("*.json"):
            try:
                with path.open("r") as f:
                    data = json.load(f)
                session = CollaborativeSession.from_dict(data)
                self._sessions[session.session_id] = session
            except Exception:
                pass

    def list_sessions(self) -> list[CollaborativeSession]:
        """List all collaborative sessions."""
        return sorted(
            self._sessions.values(),
            key=lambda s: s.updated_at,
            reverse=True,
        )

    def get_user_sessions(self, user_id: str) -> list[CollaborativeSession]:
        """Get sessions for a specific user.

        Args:
            user_id: User ID

        Returns:
            List of sessions the user participates in
        """
        return [
            s for s in self._sessions.values()
            if any(p.user_id == user_id for p in s.participants)
        ]


# =============================================================================
# REAL-TIME SYNC SUPPORT
# =============================================================================


@dataclass
class SyncEvent:
    """An event for real-time synchronization."""

    event_id: str
    session_id: str
    event_type: str
    payload: dict[str, Any]
    author_id: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "author_id": self.author_id,
            "timestamp": self.timestamp.isoformat(),
        }


class SyncAdapter:
    """Adapter for real-time synchronization.

    Override this class to integrate with your preferred
    real-time infrastructure (WebSocket, SSE, etc.).
    """

    def __init__(self, session_id: str):
        """Initialize the adapter.

        Args:
            session_id: Session to sync
        """
        self.session_id = session_id
        self._event_handlers: list[Callable[[SyncEvent], None]] = []

    def emit(self, event: SyncEvent):
        """Emit an event to all connected clients.

        Override this to implement actual network transmission.
        """
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                pass

    def on_event(self, handler: Callable[[SyncEvent], None]):
        """Register an event handler.

        Args:
            handler: Callback for incoming events
        """
        self._event_handlers.append(handler)

    def create_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        author_id: str,
    ) -> SyncEvent:
        """Create a sync event.

        Args:
            event_type: Type of event
            payload: Event data
            author_id: Author of the event

        Returns:
            Created SyncEvent
        """
        event_id = hashlib.sha256(
            f"{self.session_id}:{event_type}:{time.time()}".encode()
        ).hexdigest()[:12]

        return SyncEvent(
            event_id=event_id,
            session_id=self.session_id,
            event_type=event_type,
            payload=payload,
            author_id=author_id,
        )


# =============================================================================
# INVITATION MANAGEMENT
# =============================================================================


@dataclass
class Invitation:
    """An invitation to join a collaborative session."""

    invite_id: str
    session_id: str
    inviter_id: str
    invitee_email: str
    role: ParticipantRole
    message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    accepted: bool = False


class InvitationManager:
    """Manages invitations to collaborative sessions."""

    def __init__(self, collaboration_manager: CollaborationManager):
        """Initialize the manager.

        Args:
            collaboration_manager: The collaboration manager
        """
        self.collab = collaboration_manager
        self._invitations: dict[str, Invitation] = {}

    def create_invitation(
        self,
        session_id: str,
        inviter_id: str,
        invitee_email: str,
        role: ParticipantRole = ParticipantRole.REVIEWER,
        message: str = "",
        expires_hours: int = 72,
    ) -> Invitation | None:
        """Create an invitation.

        Args:
            session_id: Session ID
            inviter_id: ID of user sending invite
            invitee_email: Email of invitee
            role: Role to assign
            message: Optional message
            expires_hours: Hours until expiration

        Returns:
            Created invitation or None
        """
        session = self.collab.get_session(session_id)
        if not session:
            return None

        # Verify inviter has permission
        inviter = next((p for p in session.participants if p.user_id == inviter_id), None)
        if not inviter or inviter.role not in [ParticipantRole.OWNER, ParticipantRole.EDITOR]:
            return None

        invite_id = hashlib.sha256(
            f"{session_id}:{invitee_email}:{time.time()}".encode()
        ).hexdigest()[:16]

        from datetime import timedelta
        expires = datetime.now() + timedelta(hours=expires_hours)

        invitation = Invitation(
            invite_id=invite_id,
            session_id=session_id,
            inviter_id=inviter_id,
            invitee_email=invitee_email,
            role=role,
            message=message,
            expires_at=expires,
        )

        self._invitations[invite_id] = invitation
        return invitation

    def accept_invitation(
        self,
        invite_id: str,
        user_id: str,
        user_name: str,
    ) -> Participant | None:
        """Accept an invitation.

        Args:
            invite_id: Invitation ID
            user_id: ID of accepting user
            user_name: Name of accepting user

        Returns:
            Added participant or None
        """
        invitation = self._invitations.get(invite_id)
        if not invitation:
            return None

        # Check expiration
        if invitation.expires_at and datetime.now() > invitation.expires_at:
            return None

        if invitation.accepted:
            return None

        # Add participant
        participant = self.collab.add_participant(
            invitation.session_id,
            user_id,
            user_name,
            email=invitation.invitee_email,
            role=invitation.role,
        )

        if participant:
            invitation.accepted = True

        return participant

    def get_pending_invitations(self, session_id: str) -> list[Invitation]:
        """Get pending invitations for a session.

        Args:
            session_id: Session ID

        Returns:
            List of pending invitations
        """
        now = datetime.now()
        return [
            inv for inv in self._invitations.values()
            if inv.session_id == session_id
            and not inv.accepted
            and (inv.expires_at is None or inv.expires_at > now)
        ]
