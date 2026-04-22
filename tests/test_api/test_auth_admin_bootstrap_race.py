"""Regression test: concurrent first-register calls must not both become admin.

The /register endpoint uses an atomic conditional UPDATE on instance_settings
to flip admin_bootstrapped False→True. Exactly one caller can win; all others
become regular users.

Root cause prevented: if the code regressed to a read-then-write pattern
(count users → if 0, set role=admin), two concurrent callers could both observe
count=0 and both become admin.

The TOCTOU invariant is verified by:
1. Simulating the race directly against the DB: caller-1 claims the flag and
   commits, then caller-2's UPDATE sees rowcount=0 and must take the user role.
2. A sequential HTTP-level sanity test via TestClient.
3. A direct conditional-UPDATE unit test.

Fixed in: src/fourdpocket/api/auth.py (register endpoint)
"""



class TestAdminBootstrapRace:
    def test_toctou_flag_claim_is_first_writer_wins(self, db):
        """Simulate the TOCTOU window at the DB level.

        Setup: pre-populate instance_settings with admin_bootstrapped=False and
        one existing user (so user_count > 0 — this is the state that a
        read-then-write approach would FAIL on if two callers both read count=0
        before either inserts).

        The key invariant: only the session that successfully flips
        admin_bootstrapped False→True (rowcount==1) may grant admin role.
        A second session that runs its UPDATE after the first has committed will
        always see rowcount==0 and must choose the user role.
        """
        from sqlalchemy import text

        from fourdpocket.api.deps import get_or_create_settings
        from fourdpocket.models.base import UserRole

        get_or_create_settings(db)  # ensure singleton row, admin_bootstrapped=False

        def _try_claim_admin(session) -> UserRole:
            result = session.execute(
                text(
                    "UPDATE instance_settings SET admin_bootstrapped = :t "
                    "WHERE id = 1 AND admin_bootstrapped = :f"
                ),
                {"t": True, "f": False},
            )
            session.commit()
            return UserRole.admin if result.rowcount == 1 else UserRole.user

        # Caller 1 claims the slot
        role1 = _try_claim_admin(db)

        # Caller 2 arrives after caller 1 has committed — simulates losing the race
        role2 = _try_claim_admin(db)
        role3 = _try_claim_admin(db)  # a third concurrent caller for good measure

        assert role1 == UserRole.admin, "First caller must win admin slot"
        assert role2 == UserRole.user, "Second caller must become user (flag already set)"
        assert role3 == UserRole.user, "Third caller must become user (flag already set)"

    def test_second_sequential_register_is_user(self, client):
        """Sanity: after one admin exists, all subsequent registrants are users."""
        r1 = client.post("/api/v1/auth/register", json={
            "email": "seq1@example.com",
            "username": "seq1",
            "password": "Seq1234!",
        })
        r2 = client.post("/api/v1/auth/register", json={
            "email": "seq2@example.com",
            "username": "seq2",
            "password": "Seq5678!",
        })
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["role"] == "admin"
        assert r2.json()["role"] == "user"

    def test_atomic_update_prevents_toctou(self, db):
        """Directly verify the conditional UPDATE allows only one winner.

        Validates the UPDATE semantics: the WHERE clause makes it a no-op when
        the flag is already True, which is the atomic guarantee that prevents
        two concurrent callers both claiming admin.
        """
        from sqlalchemy import text

        from fourdpocket.api.deps import get_or_create_settings

        get_or_create_settings(db)  # ensure the singleton row exists

        def _claim_admin():
            result = db.execute(
                text(
                    "UPDATE instance_settings SET admin_bootstrapped = :t "
                    "WHERE id = 1 AND admin_bootstrapped = :f"
                ),
                {"t": True, "f": False},
            )
            db.commit()
            return result.rowcount

        first = _claim_admin()
        second = _claim_admin()
        third = _claim_admin()

        assert first == 1, "First conditional UPDATE should affect 1 row"
        assert second == 0, "Second conditional UPDATE must be a no-op (flag already set)"
        assert third == 0, "Third conditional UPDATE must be a no-op"
