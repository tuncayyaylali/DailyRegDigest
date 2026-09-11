const fs = require('fs');
const { execSync } = require('child_process');

console.log('=== Official Gazette AI: Initializing Automated n8n Setup ===');

const geminiKey = process.env.GEMINI_API_KEY;
const gmailClientId = process.env.GMAIL_CLIENT_ID;
const gmailClientSecret = process.env.GMAIL_CLIENT_SECRET;

const credsToImport = [];

// 1. Google Gemini Credential
if (geminiKey && geminiKey.trim()) {
  console.log('-> GEMINI_API_KEY detected, configuring n8n Gemini credentials...');
  credsToImport.push({
    id: '3HvkqFv1R1yU4a1Y',
    name: 'Google Gemini(PaLM) Api account',
    type: 'googlePalmApi',
    data: {
      apiKey: geminiKey.trim()
    }
  });
}

// 2. Gmail OAuth2 Credential (GCP Console Client ID & Secret)
if (gmailClientId && gmailClientSecret) {
  console.log('-> GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET detected, configuring n8n Gmail OAuth2 credential...');
  
  // Preserve existing OAuth token if available
  let existingOauthData = null;
  try {
    const rawExport = execSync('n8n export:credentials --id=Mmsf5KIYDPmYDmAB --decrypted', { 
      encoding: 'utf-8', 
      stdio: ['pipe', 'pipe', 'ignore'] 
    });
    const parsed = JSON.parse(rawExport);
    if (parsed[0] && parsed[0].data && parsed[0].data.oauthTokenData) {
      existingOauthData = parsed[0].data.oauthTokenData;
    }
  } catch (e) {
    // Fresh setup might not have token data yet
  }

  const gmailData = {
    clientId: gmailClientId.trim(),
    clientSecret: gmailClientSecret.trim()
  };
  if (existingOauthData) {
    gmailData.oauthTokenData = existingOauthData;
    console.log('-> [Gmail] Existing Google OAuth session token detected and preserved.');
  } else {
    console.log('-> [Gmail] First-time setup: Please visit http://localhost:5678/credentials, open "Gmail account", and click "Sign in with Google" once.');
  }

  credsToImport.push({
    id: 'Mmsf5KIYDPmYDmAB',
    name: 'Gmail account',
    type: 'gmailOAuth2',
    data: gmailData
  });
}

// 3. PostgreSQL Credential (Gazette DB)
const dbHost = process.env.DB_HOST || 'postgres';
const dbName = process.env.POSTGRES_DB || 'gazette_db';
const dbUser = process.env.POSTGRES_USER || 'postgres';
const dbPass = process.env.POSTGRES_PASSWORD || 'postgres';

console.log('-> Configuring PostgreSQL credentials (gazette_db_cred)...');
credsToImport.push({
  id: 'gazette_db_cred',
  name: 'Gazette DB',
  type: 'postgres',
  data: {
    host: dbHost,
    database: dbName,
    user: dbUser,
    password: dbPass,
    port: 5432,
    ssl: 'disable'
  }
});

// Import credentials
if (credsToImport.length > 0) {
  const tmpPath = '/tmp/auto_credentials.json';
  fs.writeFileSync(tmpPath, JSON.stringify(credsToImport, null, 2));
  try {
    execSync(`n8n import:credentials --input=${tmpPath}`, { stdio: 'inherit' });
    console.log(`-> Successfully imported ${credsToImport.length} credentials into n8n vault.`);
  } catch (err) {
    console.error('-> Credential import error:', err.message);
  } finally {
    try { fs.unlinkSync(tmpPath); } catch (_) {}
  }
}

// 4. Import Workflow
const workflowPath = '/data/workflows/gazette_tracker_workflow.json';
if (fs.existsSync(workflowPath)) {
  console.log('-> Checking and synchronizing workflow:', workflowPath);
  try {
    execSync(`n8n import:workflow --input=${workflowPath}`, { stdio: 'inherit' });
    console.log('-> Workflow synchronized successfully.');
  } catch (err) {
    console.error('-> Workflow import error:', err.message);
  }
}

console.log('=== Starting n8n Server ===\n');

