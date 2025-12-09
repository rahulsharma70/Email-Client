# SMTP Server Selection Feature - ANAGHA SOLUTION

## ✅ Feature Implemented

**SMTP Server Selection with Checkboxes** - Select exactly 4 SMTP servers for each batch of 80 emails.

## 🎯 How It Works

### For First Batch (80 Emails):
1. Go to **Campaign Builder**
2. Select **exactly 4 SMTP servers** using checkboxes
3. Create campaign with 80 recipients
4. System distributes: 20 emails per selected server

### For Second Batch (Another 80 Emails):
1. Go to **Campaign Builder** again
2. Select **different 4 SMTP servers** (or same 4)
3. Create another campaign with 80 recipients
4. System distributes: 20 emails per selected server

## 📍 Location

**Campaign Builder Page** - New section: "Select SMTP Servers"

## 🎨 UI Features

### Checkbox Selection:
- **Visual cards** for each SMTP server
- Shows server name, username, and host:port
- **Green highlight** when selected
- **Counter**: Shows "X/4 selected"
- **Validation**: Prevents selecting more than 4

### Visual Feedback:
- **0/4 selected** - Blue (not started)
- **1-3/4 selected** - Orange (in progress)
- **4/4 selected** - Green (ready)

### Error Messages:
- Shows error if trying to select more than 4
- Shows error if less than 4 when submitting
- Clear validation messages

## 📋 Step-by-Step Usage

### Step 1: Configure SMTP Servers
1. Go to **SMTP Config** page
2. Add at least 8 SMTP servers (for 2 batches)
3. Make sure all are **Active**

### Step 2: Upload Recipients
1. Go to **Recipients** page
2. Upload 80 email IDs (or more)

### Step 3: Create First Campaign (80 Emails)
1. Go to **Campaign Builder**
2. Fill in campaign details
3. **Select 4 SMTP servers** (checkboxes)
4. Create and send campaign
5. System sends: 20 emails per selected server

### Step 4: Create Second Campaign (Another 80 Emails)
1. Go to **Campaign Builder** again
2. Fill in campaign details
3. **Select another 4 SMTP servers** (different or same)
4. Create and send campaign
5. System sends: 20 emails per selected server

## 🔧 Technical Details

### Distribution Logic:
- **Selected servers only** - Uses only the 4 selected servers
- **Round-robin** - Distributes evenly (20 per server)
- **Automatic** - No manual assignment needed

### API Changes:
- `add_to_queue()` now accepts `selected_smtp_servers` parameter
- Campaign creation API handles selected servers
- Validates exactly 4 servers before sending

## ✅ Benefits

1. **Flexible Selection** - Choose which servers to use for each batch
2. **Load Distribution** - Spread emails across selected servers
3. **Batch Management** - Different servers for different batches
4. **Visual Interface** - Easy to see and select servers
5. **Validation** - Prevents errors (must select exactly 4)

## 📊 Example Scenarios

### Scenario 1: Two Batches with Different Servers
- **Batch 1**: Select Servers 1, 2, 3, 4 → Send 80 emails
- **Batch 2**: Select Servers 5, 6, 7, 8 → Send another 80 emails

### Scenario 2: Two Batches with Same Servers
- **Batch 1**: Select Servers 1, 2, 3, 4 → Send 80 emails
- **Batch 2**: Select Servers 1, 2, 3, 4 again → Send another 80 emails

### Scenario 3: Overlapping Servers
- **Batch 1**: Select Servers 1, 2, 3, 4 → Send 80 emails
- **Batch 2**: Select Servers 3, 4, 5, 6 → Send another 80 emails

## 🎯 Validation Rules

- ✅ Must select **exactly 4 servers** before sending
- ✅ Only **active servers** are shown
- ✅ Cannot select more than 4 servers
- ✅ Clear error messages if validation fails

## 🚀 Ready to Use!

The feature is fully implemented. You can now:
1. ✅ Select 4 SMTP servers for first 80 emails
2. ✅ Select another 4 SMTP servers for next 80 emails
3. ✅ Visual checkbox interface
4. ✅ Automatic distribution (20 per server)

All ready for your workflow! 🎉

