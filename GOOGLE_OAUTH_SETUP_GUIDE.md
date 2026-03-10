# 🔧 Google OAuth Setup - Step by Step Guide

## Issue: "Access Blocked" or "App Access Invalid"

This happens when OAuth URLs aren't configured correctly. Follow these exact steps:

---

## 📍 Step 1: Go to Google Cloud Console

1. Open: https://console.cloud.google.com/
2. Make sure you're logged in with the correct Google account
3. Select your project (or find "Brain Desk" project)

---

## 📍 Step 2: Configure OAuth Consent Screen

### Navigate:
```
Google Cloud Console → APIs & Services → OAuth consent screen
```

**Direct Link:** https://console.cloud.google.com/apis/credentials/consent

### What to Check:

1. **User Type:** 
   - If you see "Internal" → Change to **"External"**
   - Click "MAKE EXTERNAL" if needed

2. **Publishing Status:**
   - If it says "Testing" → That's OK for now
   - Click "EDIT APP" to modify settings

3. **App Information:**
   - App name: `Brain Desk`
   - User support email: Your email
   - Developer contact: Your email

4. **Scopes:** Click "ADD OR REMOVE SCOPES" and add these:
   ```
   https://www.googleapis.com/auth/userinfo.email
   https://www.googleapis.com/auth/userinfo.profile
   https://www.googleapis.com/auth/classroom.courses.readonly
   https://www.googleapis.com/auth/classroom.coursework.me.readonly
   https://www.googleapis.com/auth/classroom.coursework.students.readonly
   https://www.googleapis.com/auth/drive.readonly
   https://www.googleapis.com/auth/calendar
   ```

5. **Test Users (IMPORTANT):**
   - Scroll down to "Test users"
   - Click "ADD USERS"
   - **Add YOUR Google email address** that you'll use to login
   - Click "SAVE"

6. Click "SAVE AND CONTINUE" through all steps

---

## 📍 Step 3: Configure OAuth Credentials

### Navigate:
```
Google Cloud Console → APIs & Services → Credentials
```

**Direct Link:** https://console.cloud.google.com/apis/credentials

### Find Your OAuth Client:

1. Look for your OAuth 2.0 Client ID:
   - Name might be "Web client 1" or similar
   - Client ID starts with: `954627207327-...`

2. Click the **pencil icon (✏️)** or the name to edit

### Add Authorized Origins:

Scroll to **"Authorized JavaScript origins"**

Click **"+ ADD URI"** and add:
```
https://brain-desk-1.preview.emergentagent.com
```

**IMPORTANT:** No trailing slash!

### Add Authorized Redirect URIs:

Scroll to **"Authorized redirect URIs"**

Click **"+ ADD URI"** and add BOTH:
```
https://brain-desk-1.preview.emergentagent.com/api/auth/callback
https://brain-desk-1.preview.emergentagent.com/auth/google/callback
```

### Final Check:
```
Authorized JavaScript origins:
✅ https://brain-desk-1.preview.emergentagent.com

Authorized redirect URIs:
✅ https://brain-desk-1.preview.emergentagent.com/api/auth/callback
✅ https://brain-desk-1.preview.emergentagent.com/auth/google/callback
```

3. Click **"SAVE"** at the bottom

---

## 📍 Step 4: Enable Required APIs

### Navigate:
```
Google Cloud Console → APIs & Services → Library
```

**Direct Link:** https://console.cloud.google.com/apis/library

### Enable these APIs (search and click "ENABLE" for each):

1. **Google+ API** (for OAuth)
   - Search: "Google+ API"
   - Click it → Click "ENABLE"

2. **Google Classroom API**
   - Search: "Google Classroom API"
   - Click it → Click "ENABLE"

3. **Google Drive API**
   - Search: "Google Drive API"
   - Click it → Click "ENABLE"

4. **Google Calendar API**
   - Search: "Google Calendar API"
   - Click it → Click "ENABLE"

---

## 🎯 Quick Navigation Links

### Use these direct links (make sure you're in the right project):

1. **OAuth Consent Screen:**
   https://console.cloud.google.com/apis/credentials/consent

2. **Credentials:**
   https://console.cloud.google.com/apis/credentials

3. **API Library:**
   https://console.cloud.google.com/apis/library

4. **Enabled APIs:**
   https://console.cloud.google.com/apis/dashboard

---

## ✅ Verification Checklist

After making changes, verify:

- [ ] OAuth consent screen is set to "External"
- [ ] Your email is added as a test user
- [ ] All required scopes are added
- [ ] JavaScript origin is added (no trailing slash)
- [ ] Redirect URIs are added (with /api/auth/callback)
- [ ] All 4 APIs are enabled (Google+, Classroom, Drive, Calendar)
- [ ] You clicked "SAVE" on credentials page

---

## 🔄 After Making Changes

1. Wait 1-2 minutes for Google to propagate changes
2. Clear your browser cache or use incognito mode
3. Try logging in again: https://brain-desk-1.preview.emergentagent.com

---

## 🚨 Common Mistakes

❌ **Don't do this:**
- Adding `http://` instead of `https://`
- Adding trailing slash: `...com/` ❌
- Forgetting to add yourself as test user
- Not enabling all required APIs

✅ **Do this:**
- Use exact URLs without trailing slashes
- Add yourself as test user
- Enable all APIs
- Wait 1-2 minutes after saving

---

## 🆘 Still Not Working?

If you still get errors, send me:
1. Screenshot of your "Authorized JavaScript origins" section
2. Screenshot of your "Authorized redirect URIs" section
3. Screenshot of "Test users" section
4. The exact error message you see

---

## 📱 Test the Login

After setup, test here:
https://brain-desk-1.preview.emergentagent.com

Click "Continue with Google" and you should see the OAuth consent screen!

---

**Need Help?** Let me know which step you're stuck on! 🙋‍♂️
