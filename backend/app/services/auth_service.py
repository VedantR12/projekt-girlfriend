from app.services.db import supabase_anon

# ──────────────────────────────────────────
# Supabase Auth Service
# Uses the ANON client (not service key)
# ──────────────────────────────────────────


def signup_with_email(email: str, password: str):
    """
    Create a new user with email + password.
    Returns Supabase auth response (contains session + user).
    """
    try:
        response = supabase_anon.auth.sign_up({
            "email": email,
            "password": password
        })

        if response.user is None:
            return {"error": "Signup failed — user is None"}

        return {
            "user_id": response.user.id,
            "email": response.user.email,
            "access_token": response.session.access_token if response.session else None,
            "refresh_token": response.session.refresh_token if response.session else None,
            "message": "Signup successful. Check email for confirmation if email verification is enabled."
        }

    except Exception as e:
        return {"error": str(e)}


def login_with_email(email: str, password: str):
    """
    Login with email + password.
    Returns access_token + refresh_token.
    """
    try:
        response = supabase_anon.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if response.user is None:
            return {"error": "Login failed — invalid credentials"}

        return {
            "user_id": response.user.id,
            "email": response.user.email,
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token
        }

    except Exception as e:
        return {"error": str(e)}


def get_google_oauth_url(redirect_to: str = None):
    """
    Get the Google OAuth URL. Frontend redirects user to this URL.
    After auth, Supabase redirects back to the redirect_to URL with tokens.
    """
    try:
        options = {}
        if redirect_to:
            options["redirect_to"] = redirect_to

        response = supabase_anon.auth.sign_in_with_oauth({
            "provider": "google",
            "options": options
        })

        return {"url": response.url}

    except Exception as e:
        return {"error": str(e)}


def refresh_session(refresh_token: str):
    """
    Get a new access_token using a refresh_token.
    """
    try:
        response = supabase_anon.auth.refresh_session(refresh_token)

        if response.session is None:
            return {"error": "Failed to refresh session"}

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token
        }

    except Exception as e:
        return {"error": str(e)}
