# ASHA-SATHI AI — Web Prototype V3

**Frontend:** HTML, CSS, JavaScript · **Backend:** Python Flask · **Database:** SQLite

## Added in V3
- ASHA worker registration, admin approval and secure password hashing.
- Worker-specific patient and visit records.
- Voice-to-EHR browser dictation using the Web Speech API (Chrome recommended): Hindi, Indian English and Marathi options; transcript appears in the form and must be reviewed before saving.
- Area request intake with priority and optional patient link.
- Admin location-wise workload grouped by district → block → village.
- Admin can update request status: Open, In Progress, Resolved.

## Update / run
Extract into a new folder such as `D:\ASHA_SATHI_AI_WEB_V3`, open it in VS Code.
In PowerShell:
`py -m venv venv`
`.\venv\Scripts\python.exe -m pip install -r requirements.txt`
`.\venv\Scripts\python.exe app.py`
Open `http://127.0.0.1:5000`.

## Admin demo login
Username: `ADMIN`
Password: `ChangeMe123!`
Change before any deployment.

## Worker approval flow
1. Register worker at `/register`.
2. Admin signs in at `/admin-login`.
3. Approve worker.
4. Worker logs in with Worker ID or registered mobile and password.

## Voice EHR notes
The Studio uses the browser Web Speech API. Chrome support and microphone permission are needed; recognition may rely on browser/network services and may not work offline. The ASHA worker must review/correct the transcript. The current version does not yet call Gemini to convert transcript into validated structured clinical fields. That is the next AI integration milestone.

## Location workload
Workers are associated with State, District, Block, Village and PHC during registration. Requests are automatically tagged with that assigned area. Admin sees counts grouped by District/Block/Village and can update request status. This first version is an area workload queue, not a live GPS dispatch system. For accurate routing later, add verified PHC/village master data and optional GPS coordinates with consent.

## Data and safety
SQLite file: `data/asha_sathi.db`. Back it up before updates. `CREATE TABLE IF NOT EXISTS` and a safe additive migration are used; do not delete the DB to fix errors.
Use fictional demo data only. Do not put identifiable patient information into hackathon demos. Not a production clinical system, not a diagnostic tool, and no ABDM/FHIR certification is claimed. Real deployment needs HTTPS, CSRF protection, admin credential rotation, backups, audit controls, role review and privacy/security assessment.
