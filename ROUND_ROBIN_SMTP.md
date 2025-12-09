# Round-Robin SMTP Distribution - ANAGHA SOLUTION

## ✅ Feature Implemented

**Automatic SMTP Server Rotation** - Emails are automatically distributed across multiple SMTP servers in a round-robin fashion.

## 🎯 How It Works

### Scenario:
- **4 SMTP servers** configured
- **80 recipient emails** to send
- **20 emails per server** (configurable)

### Distribution:
1. **Server 1** sends emails **1-20**
2. **Server 2** sends emails **21-40**
3. **Server 3** sends emails **41-60**
4. **Server 4** sends emails **61-80**

The system automatically rotates through all active SMTP servers.

## 📋 Setup Instructions

### Step 1: Configure 4 SMTP Servers
1. Go to **SMTP Config** page
2. Add 4 email accounts with:
   - Outgoing server settings (SMTP)
   - Incoming server settings (IMAP/POP3)
   - Username and password
   - Make sure all are **Active**

### Step 2: Upload 80 Recipients
1. Go to **Recipients** page
2. Import your 80 email IDs via CSV/Excel
3. Or add them manually

### Step 3: Create Campaign
1. Go to **Campaign Builder**
2. Create your email campaign
3. Click **"Create & Send Campaign"**
4. The system will automatically:
   - Distribute 20 emails to Server 1
   - Distribute 20 emails to Server 2
   - Distribute 20 emails to Server 3
   - Distribute 20 emails to Server 4

## 🔧 Technical Details

### Round-Robin Algorithm
- Formula: `server_index = (email_index // emails_per_server) % num_servers`
- Each server gets exactly `emails_per_server` emails (default: 20)
- Distribution is automatic and balanced

### Configuration
- **Default emails per server:** 20
- **Configurable:** Yes (can be changed in code)
- **Automatic:** Yes, no manual intervention needed

## 📊 Distribution Example

For 80 emails across 4 servers:

```
Email 1-20   → Server 1
Email 21-40  → Server 2
Email 41-60  → Server 3
Email 61-80  → Server 4
```

For 100 emails across 4 servers (20 per server):

```
Email 1-20   → Server 1
Email 21-40  → Server 2
Email 41-60  → Server 3
Email 61-80  → Server 4
Email 81-100 → Server 1 (wraps around)
```

## ✅ Benefits

1. **Load Distribution** - Spreads email load across multiple servers
2. **Rate Limit Compliance** - Helps avoid hitting per-server rate limits
3. **Automatic** - No manual configuration needed
4. **Balanced** - Even distribution across all servers
5. **Scalable** - Works with any number of servers and emails

## 🔍 Verification

After creating a campaign, check the console output:

```
📧 Distributing 80 emails across 4 SMTP servers
   20 emails per server
   Email 1: Assigned to SMTP Server 1 (Server Name)
   Email 21: Assigned to SMTP Server 2 (Server Name)
   Email 41: Assigned to SMTP Server 3 (Server Name)
   Email 61: Assigned to SMTP Server 4 (Server Name)

📊 Email Distribution:
   Server 1 (Server Name): 20 emails
   Server 2 (Server Name): 20 emails
   Server 3 (Server Name): 20 emails
   Server 4 (Server Name): 20 emails
```

## 🎯 Use Cases

- **Bulk Email Sending** - Distribute load across multiple accounts
- **Rate Limit Avoidance** - Stay within per-account sending limits
- **High Volume** - Send large campaigns efficiently
- **Account Rotation** - Automatically rotate through email accounts

## 📝 Notes

- Only **active** SMTP servers are used
- Servers must have valid credentials
- Distribution is based on server order (ID)
- Each server processes its assigned emails sequentially
- If a server fails, only its assigned emails are affected

## 🚀 Ready to Use!

The system is now configured for automatic round-robin distribution. Just:
1. Add your 4 SMTP servers
2. Upload 80 recipients
3. Create and send your campaign
4. Watch the automatic distribution! 🎉

