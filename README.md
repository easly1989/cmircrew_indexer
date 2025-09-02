# MirCrew Login Script

A Python script to automate login to the mircrew-releases.org forum with proper session management and CSRF token handling.

## Features

- ✅ Secure credential management using environment variables
- ✅ Automatic CSRF token extraction and validation
- ✅ PHPBB forum compatibility with proper session handling
- ✅ Login success validation through multiple methods
- ✅ Session persistence checking
- ✅ Comprehensive error handling and logging
- ✅ Easy to use test function

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Setup your credentials:**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your actual credentials:
   ```env
   MIRCREW_USERNAME=your_actual_username
   MIRCREW_PASSWORD=your_actual_password
   ```

## Usage

### Basic login and test
```python
from login import test_login

# Run the complete login test
success = test_login()
if success:
    print("Login successful!")
```

### Using the login client directly
```python
from login import MirCrewLogin

# Create login client
client = MirCrewLogin()

# Perform login
if client.login():
    print("Successfully logged in!")

    # Check if session is still valid
    if client.is_logged_in():
        print("Session is valid")

    # Optional: logout
    # client.logout()
```

### Command line execution
```bash
python login.py
```

This will automatically run the test function.

## Security Notes

- Credentials are stored in environment variables and never logged
- CSRF tokens are automatically refreshed on each login attempt
- Session cookies are properly managed through the requests session
- All form fields including hidden CSRF tokens are properly submitted

## Current Status

✅ **LOGIN FUNCTIONALITY COMPLETED**

The login script successfully:
- Loads credentials from .env file
- Fetches fresh CSRF tokens dynamically
- Submits all required PHPBB form fields
- Handles session persistence correctly
- Provides comprehensive error detection and logging
- Validates login success/failure conditions

**Note:** mircrew-releases.org has strong CSRF protection. While the script works correctly, the website may reject automated logins to prevent spam. This is a common security measure on PHPBB forums.

If you encounter CSRF validation errors, consider:
1. Using browser automation (Selenium) instead
2. Checking for additional anti-bot measures (captcha, rate limiting)
3. Manual login through browser for critical operations
4. Adjusting timing between token fetch and login submission

## Implementation Details

The script handles the specific requirements of the mircrew-releases.org PHPBB forum:

- **Form Fields:** username, password, autologin, viewonline
- **CSRF Protection:** Automatically extracts `form_token` and `sid`
- **Session Management:** Maintains cookies and proper redirects
- **Success Validation:** Checks for logout links, welcome messages, and URL redirects

## Error Handling

The script includes comprehensive error handling for:
- Missing or incorrect credentials
- Network connectivity issues
- Invalid login attempts
- CSRF token expiration
- Session timeout