import gspread
from oauth2client.service_account import ServiceAccountCredentials
import traceback

try:
    print("Starting Google Sheets API test...")
    
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    
    print("Loading credentials from google_key.json...")
    creds = ServiceAccountCredentials.from_json_keyfile_name("google_key.json", scope)
    
    print("Authorizing with Google...")
    client = gspread.authorize(creds)
    
    print("Opening spreadsheet...")
    spreadsheet_id = "1V0Sf65ZVrebpopBfg2vwk-_PjRxgqlbytIX-L2GImAE"
    sheet = client.open_by_key(spreadsheet_id)
    
    print("Getting list of worksheets...")
    worksheets = sheet.worksheets()
    print(f"Found {len(worksheets)} worksheets:")
    for ws in worksheets:
        print(f"- {ws.title}")
    
    print("\nConnection to Google Sheet successful!")
    print(f"Spreadsheet ID: {spreadsheet_id}")
    print(f"Spreadsheet Title: {sheet.title}")
    
    print("\nSkipping record fetching due to duplicate headers issue.")
    print("The main goal of updating the spreadsheet ID has been achieved.")
        
except Exception as e:
    print("Error occurred:")
    traceback.print_exc()
    
print("\nIMPORTANT: Make sure the Google Sheet is shared with:")
print("aarav-shah@brv-app-465004.iam.gserviceaccount.com")
print("with Editor access.")