"""Tests for the Socratic collaboration module.

Copyright 2026 Smart-AI-Memory
Licensed under Fair Source License 0.9
"""

import pytest
from datetime import datetime


class TestParticipantRole:
    """Tests for ParticipantRole enum."""

    def test_all_roles_exist(self):
        """Test all expected roles exist."""
        from empathy_os.socratic.collaboration import ParticipantRole

        assert hasattr(ParticipantRole, "OWNER")
        assert hasattr(ParticipantRole, "EDITOR")
        assert hasattr(ParticipantRole, "REVIEWER")
        assert hasattr(ParticipantRole, "VIEWER")

    def test_role_values(self):
        """Test role values."""
        from empathy_os.socratic.collaboration import ParticipantRole

        assert ParticipantRole.OWNER.value == "owner"
        assert ParticipantRole.EDITOR.value == "editor"


class TestVoteType:
    """Tests for VoteType enum."""

    def test_all_vote_types_exist(self):
        """Test all expected vote types exist."""
        from empathy_os.socratic.collaboration import VoteType

        assert hasattr(VoteType, "APPROVE")
        assert hasattr(VoteType, "REJECT")
        assert hasattr(VoteType, "ABSTAIN")


class TestChangeType:
    """Tests for ChangeType enum."""

    def test_all_change_types_exist(self):
        """Test all expected change types exist."""
        from empathy_os.socratic.collaboration import ChangeType

        assert hasattr(ChangeType, "ADD_AGENT")
        assert hasattr(ChangeType, "REMOVE_AGENT")
        assert hasattr(ChangeType, "MODIFY_AGENT")
        assert hasattr(ChangeType, "ADD_CONNECTION")
        assert hasattr(ChangeType, "REMOVE_CONNECTION")


class TestParticipant:
    """Tests for Participant dataclass."""

    def test_create_participant(self):
        """Test creating a participant."""
        from empathy_os.socratic.collaboration import Participant, ParticipantRole

        participant = Participant(
            user_id="user-001",
            name="Alice",
            email="alice@example.com",
            role=ParticipantRole.EDITOR,
        )

        assert participant.user_id == "user-001"
        assert participant.name == "Alice"
        assert participant.role == ParticipantRole.EDITOR

    def test_participant_default_role(self):
        """Test participant default role is viewer."""
        from empathy_os.socratic.collaboration import Participant, ParticipantRole

        participant = Participant(
            user_id="user-002",
            name="Bob",
        )

        assert participant.role == ParticipantRole.VIEWER

    def test_participant_permissions(self):
        """Test participant permissions based on role."""
        from empathy_os.socratic.collaboration import Participant, ParticipantRole

        owner = Participant(user_id="1", name="Owner", role=ParticipantRole.OWNER)
        editor = Participant(user_id="2", name="Editor", role=ParticipantRole.EDITOR)
        reviewer = Participant(
            user_id="3", name="Reviewer", role=ParticipantRole.REVIEWER
        )
        viewer = Participant(user_id="4", name="Viewer", role=ParticipantRole.VIEWER)

        assert owner.can_edit()
        assert editor.can_edit()
        assert not reviewer.can_edit()
        assert not viewer.can_edit()


class TestComment:
    """Tests for Comment dataclass."""

    def test_create_comment(self):
        """Test creating a comment."""
        from empathy_os.socratic.collaboration import Comment

        comment = Comment(
            comment_id="comment-001",
            author_id="user-001",
            content="This agent should have retry logic.",
            target_id="agent-001",
            target_type="agent",
        )

        assert comment.comment_id == "comment-001"
        assert comment.content == "This agent should have retry logic."

    def test_comment_reply(self):
        """Test creating a reply to a comment."""
        from empathy_os.socratic.collaboration import Comment

        parent = Comment(
            comment_id="parent-001",
            author_id="user-001",
            content="Original comment",
        )

        reply = Comment(
            comment_id="reply-001",
            author_id="user-002",
            content="I agree!",
            parent_id="parent-001",
        )

        assert reply.parent_id == parent.comment_id


class TestVote:
    """Tests for Vote dataclass."""

    def test_create_vote(self):
        """Test creating a vote."""
        from empathy_os.socratic.collaboration import Vote, VoteType

        vote = Vote(
            vote_id="vote-001",
            voter_id="user-001",
            vote_type=VoteType.APPROVE,
            target_id="change-001",
        )

        assert vote.vote_type == VoteType.APPROVE

    def test_vote_with_comment(self):
        """Test vote with optional comment."""
        from empathy_os.socratic.collaboration import Vote, VoteType

        vote = Vote(
            vote_id="vote-002",
            voter_id="user-002",
            vote_type=VoteType.REJECT,
            target_id="change-001",
            comment="Needs more testing.",
        )

        assert vote.comment == "Needs more testing."


class TestChange:
    """Tests for Change dataclass."""

    def test_create_change(self):
        """Test creating a change."""
        from empathy_os.socratic.collaboration import Change, ChangeType

        change = Change(
            change_id="change-001",
            author_id="user-001",
            change_type=ChangeType.ADD_AGENT,
            description="Added security scanner agent",
            data={"agent_id": "agent-new", "name": "Security Scanner"},
        )

        assert change.change_type == ChangeType.ADD_AGENT
        assert change.data["name"] == "Security Scanner"

    def test_change_requires_approval(self):
        """Test that significant changes require approval."""
        from empathy_os.socratic.collaboration import Change, ChangeType

        change = Change(
            change_id="change-001",
            author_id="user-001",
            change_type=ChangeType.REMOVE_AGENT,
            description="Removed agent",
            requires_approval=True,
        )

        assert change.requires_approval is True


class TestVotingResult:
    """Tests for VotingResult dataclass."""

    def test_create_voting_result(self):
        """Test creating a voting result."""
        from empathy_os.socratic.collaboration import VotingResult

        result = VotingResult(
            target_id="change-001",
            approve_count=5,
            reject_count=1,
            abstain_count=2,
            quorum_met=True,
            approved=True,
        )

        assert result.approved is True
        assert result.quorum_met is True
        assert result.approve_count == 5


class TestCollaborativeSession:
    """Tests for CollaborativeSession class."""

    def test_create_session(self, sample_session):
        """Test creating a collaborative session."""
        from empathy_os.socratic.collaboration import CollaborativeSession

        collab = CollaborativeSession(
            session_id="collab-001",
            base_session=sample_session,
        )

        assert collab.session_id == "collab-001"
        assert len(collab.participants) == 0

    def test_add_participant(self, sample_session):
        """Test adding a participant."""
        from empathy_os.socratic.collaboration import (
            CollaborativeSession,
            Participant,
            ParticipantRole,
        )

        collab = CollaborativeSession(
            session_id="collab-001",
            base_session=sample_session,
        )

        participant = Participant(
            user_id="user-001",
            name="Alice",
            role=ParticipantRole.EDITOR,
        )

        collab.add_participant(participant)

        assert len(collab.participants) == 1
        assert collab.get_participant("user-001") is not None

    def test_remove_participant(self, sample_session):
        """Test removing a participant."""
        from empathy_os.socratic.collaboration import (
            CollaborativeSession,
            Participant,
            ParticipantRole,
        )

        collab = CollaborativeSession(
            session_id="collab-001",
            base_session=sample_session,
        )

        participant = Participant(
            user_id="user-001",
            name="Alice",
            role=ParticipantRole.EDITOR,
        )

        collab.add_participant(participant)
        collab.remove_participant("user-001")

        assert len(collab.participants) == 0

    def test_add_comment(self, sample_session):
        """Test adding a comment."""
        from empathy_os.socratic.collaboration import CollaborativeSession

        collab = CollaborativeSession(
            session_id="collab-001",
            base_session=sample_session,
        )

        comment = collab.add_comment(
            author_id="user-001",
            content="Great workflow design!",
        )

        assert comment.comment_id is not None
        assert len(collab.comments) == 1

    def test_add_vote(self, sample_session):
        """Test adding a vote."""
        from empathy_os.socratic.collaboration import (
            CollaborativeSession,
            Change,
            ChangeType,
            VoteType,
        )

        collab = CollaborativeSession(
            session_id="collab-001",
            base_session=sample_session,
        )

        # Create a change to vote on
        change = collab.propose_change(
            author_id="user-001",
            change_type=ChangeType.ADD_AGENT,
            description="Add new agent",
            data={},
        )

        # Vote on it
        vote = collab.add_vote(
            voter_id="user-002",
            target_id=change.change_id,
            vote_type=VoteType.APPROVE,
        )

        assert vote is not None
        assert len(collab.votes) == 1

    def test_get_voting_result(self, sample_session):
        """Test getting voting results."""
        from empathy_os.socratic.collaboration import (
            CollaborativeSession,
            Change,
            ChangeType,
            VoteType,
            Participant,
            ParticipantRole,
        )

        collab = CollaborativeSession(
            session_id="collab-001",
            base_session=sample_session,
        )

        # Add participants
        for i in range(3):
            collab.add_participant(
                Participant(
                    user_id=f"user-{i}",
                    name=f"User {i}",
                    role=ParticipantRole.REVIEWER,
                )
            )

        # Propose a change
        change = collab.propose_change(
            author_id="user-0",
            change_type=ChangeType.ADD_AGENT,
            description="Add agent",
            data={},
        )

        # Add votes
        collab.add_vote("user-0", change.change_id, VoteType.APPROVE)
        collab.add_vote("user-1", change.change_id, VoteType.APPROVE)
        collab.add_vote("user-2", change.change_id, VoteType.REJECT)

        result = collab.get_voting_result(change.change_id)

        assert result.approve_count == 2
        assert result.reject_count == 1


class TestCollaborationManager:
    """Tests for CollaborationManager class."""

    def test_create_manager(self, storage_path):
        """Test creating a collaboration manager."""
        from empathy_os.socratic.collaboration import CollaborationManager

        manager = CollaborationManager(
            storage_path=storage_path / "collaboration.json"
        )

        assert manager is not None

    def test_create_collaborative_session(self, storage_path, sample_session):
        """Test creating a collaborative session via manager."""
        from empathy_os.socratic.collaboration import CollaborationManager

        manager = CollaborationManager(
            storage_path=storage_path / "collaboration.json"
        )

        session = manager.create_session(
            base_session=sample_session,
            owner_id="user-001",
            owner_name="Alice",
        )

        assert session.session_id is not None
        assert len(session.participants) == 1  # Owner

    def test_get_session(self, storage_path, sample_session):
        """Test getting a collaborative session."""
        from empathy_os.socratic.collaboration import CollaborationManager

        manager = CollaborationManager(
            storage_path=storage_path / "collaboration.json"
        )

        created = manager.create_session(
            base_session=sample_session,
            owner_id="user-001",
            owner_name="Alice",
        )

        retrieved = manager.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id

    def test_invite_participant(self, storage_path, sample_session):
        """Test inviting a participant."""
        from empathy_os.socratic.collaboration import (
            CollaborationManager,
            ParticipantRole,
        )

        manager = CollaborationManager(
            storage_path=storage_path / "collaboration.json"
        )

        session = manager.create_session(
            base_session=sample_session,
            owner_id="user-001",
            owner_name="Alice",
        )

        manager.invite_participant(
            session_id=session.session_id,
            inviter_id="user-001",
            invitee_id="user-002",
            invitee_name="Bob",
            role=ParticipantRole.EDITOR,
        )

        updated = manager.get_session(session.session_id)
        assert len(updated.participants) == 2

    def test_list_user_sessions(self, storage_path, sample_session):
        """Test listing sessions for a user."""
        from empathy_os.socratic.collaboration import CollaborationManager

        manager = CollaborationManager(
            storage_path=storage_path / "collaboration.json"
        )

        # Create multiple sessions
        manager.create_session(
            base_session=sample_session,
            owner_id="user-001",
            owner_name="Alice",
        )
        manager.create_session(
            base_session=sample_session,
            owner_id="user-001",
            owner_name="Alice",
        )

        sessions = manager.list_user_sessions("user-001")
        assert len(sessions) >= 2


class TestInvitationManager:
    """Tests for InvitationManager class."""

    def test_create_invitation_manager(self):
        """Test creating an invitation manager."""
        from empathy_os.socratic.collaboration import InvitationManager

        manager = InvitationManager()
        assert manager is not None

    def test_create_invitation(self):
        """Test creating an invitation."""
        from empathy_os.socratic.collaboration import InvitationManager

        manager = InvitationManager()

        invitation = manager.create_invitation(
            session_id="collab-001",
            inviter_id="user-001",
            invitee_email="bob@example.com",
        )

        assert invitation["invitation_id"] is not None
        assert invitation["token"] is not None

    def test_validate_invitation(self):
        """Test validating an invitation token."""
        from empathy_os.socratic.collaboration import InvitationManager

        manager = InvitationManager()

        invitation = manager.create_invitation(
            session_id="collab-001",
            inviter_id="user-001",
            invitee_email="bob@example.com",
        )

        is_valid = manager.validate_token(invitation["token"])
        assert is_valid is True

    def test_revoke_invitation(self):
        """Test revoking an invitation."""
        from empathy_os.socratic.collaboration import InvitationManager

        manager = InvitationManager()

        invitation = manager.create_invitation(
            session_id="collab-001",
            inviter_id="user-001",
            invitee_email="bob@example.com",
        )

        manager.revoke_invitation(invitation["invitation_id"])

        is_valid = manager.validate_token(invitation["token"])
        assert is_valid is False


class TestSyncAdapter:
    """Tests for SyncAdapter class."""

    def test_create_sync_adapter(self):
        """Test creating a sync adapter."""
        from empathy_os.socratic.collaboration import SyncAdapter

        adapter = SyncAdapter()
        assert adapter is not None

    def test_apply_change(self, sample_session):
        """Test applying a change."""
        from empathy_os.socratic.collaboration import (
            SyncAdapter,
            CollaborativeSession,
            Change,
            ChangeType,
        )

        adapter = SyncAdapter()

        collab = CollaborativeSession(
            session_id="collab-001",
            base_session=sample_session,
        )

        change = Change(
            change_id="change-001",
            author_id="user-001",
            change_type=ChangeType.ADD_AGENT,
            description="Add new agent",
            data={"name": "New Agent", "role": "helper"},
        )

        result = adapter.apply_change(collab, change)

        assert result is not None

    def test_merge_changes(self, sample_session):
        """Test merging concurrent changes."""
        from empathy_os.socratic.collaboration import (
            SyncAdapter,
            CollaborativeSession,
            Change,
            ChangeType,
        )

        adapter = SyncAdapter()

        collab = CollaborativeSession(
            session_id="collab-001",
            base_session=sample_session,
        )

        changes = [
            Change(
                change_id="change-001",
                author_id="user-001",
                change_type=ChangeType.MODIFY_AGENT,
                description="Modify agent 1",
                data={"agent_id": "agent-1"},
            ),
            Change(
                change_id="change-002",
                author_id="user-002",
                change_type=ChangeType.MODIFY_AGENT,
                description="Modify agent 2",
                data={"agent_id": "agent-2"},
            ),
        ]

        merged = adapter.merge_changes(collab, changes)

        # Should return merged state or conflict info
        assert merged is not None
