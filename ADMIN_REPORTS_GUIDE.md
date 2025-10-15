# Admin Financial Reports Guide

## Overview

The Django admin interface now includes comprehensive financial reporting functionality for tracking daily, weekly, and monthly revenue and financial metrics.

## Accessing Reports

### 1. Main Reports Dashboard

- Navigate to **Food Management > Order Details** in Django admin
- Click on **"Financial Reports"** link in the top navigation
- This will show you a dashboard with quick summaries for today, this week, and this month

### 2. Detailed Reports

From the main dashboard, you can generate detailed reports:

#### Daily Report

- Click **"Generate Daily Report"**
- Select a specific date or use today's date
- View detailed breakdown of orders, revenue, platform fees, and COD collections for that day

#### Weekly Report

- Click **"Generate Weekly Report"**
- Select a specific week or use current week
- View detailed breakdown for the entire week

#### Monthly Report

- Click **"Generate Monthly Report"**
- Select a specific month or use current month
- View detailed breakdown for the entire month

#### Custom Report

- Click **"Generate Custom Report"**
- Select start and end dates for any custom date range
- View detailed breakdown for the specified period

### 3. Admin Actions

From the Order Details list view:

- Select one or more orders
- Use the dropdown actions menu to:
  - **Generate daily report** for selected orders
  - **Generate weekly report** for selected orders
  - **Generate monthly report** for selected orders

## Report Data Included

### Summary Metrics

- **Total Orders**: Number of orders in the period
- **Total Revenue**: Sum of all order amounts
- **Platform Fee**: Total platform fees collected
- **Delivery Charges**: Total delivery charges
- **COD Collected**: Cash on delivery amounts collected
- **Average Order Value**: Revenue divided by number of orders

### Breakdowns

- **Payment Method Breakdown**: Orders and amounts by payment method (Wallet, Online, COD)
- **Delivery Status Breakdown**: Orders and amounts by delivery status
- **Daily Breakdown**: Day-by-day breakdown for the selected period
- **Top Delivery Boys**: Performance metrics for delivery agents

### COD Information

- **COD Collected**: Total COD amounts collected
- **COD Submitted**: Amounts submitted by delivery boys
- **Pending COD**: Amounts collected but not yet submitted

## Features

### Real-time Data

- All reports use real-time data from the database
- No caching - always shows current information

### Flexible Date Selection

- Support for any date range
- Default to current day/week/month
- Easy navigation between different time periods

### Export Ready

- Reports are displayed in clean, printable format
- Can be easily copied or screenshotted for external use

### Admin Integration

- Fully integrated with Django admin interface
- Consistent styling and navigation
- Proper permissions and access control

## Usage Tips

1. **Quick Overview**: Use the main dashboard for daily monitoring
2. **Detailed Analysis**: Use specific reports for deeper analysis
3. **Custom Periods**: Use custom reports for specific business periods
4. **Order Selection**: Select specific orders to generate reports for those orders only
5. **Regular Monitoring**: Check daily reports regularly to track business performance

## Technical Notes

- Reports are generated using the existing `get_financial_reports()` function
- All calculations are done in real-time
- No additional database queries beyond what's needed for the report
- Fully integrated with Django admin permissions system

## Troubleshooting

- If reports show no data, check that orders exist in the selected date range
- Ensure you have proper admin permissions to view order details
- Reports are limited to orders in the database - deleted orders won't appear

## Future Enhancements

Potential future improvements could include:

- PDF export functionality
- Email report scheduling
- Chart and graph visualizations
- Comparative period analysis
- Export to Excel/CSV formats
