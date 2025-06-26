import yfinance as yf
import pandas as pd
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import json
import os
import time

# ========================
# CONFIGURATION
# ========================
SENDER_EMAIL = os.environ.get('SENDER_EMAIL')
SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')
SERPAPI_KEY = os.environ.get('SERPAPI_KEY')  # Get free key from https://serpapi.com

# Define top stocks in each category
TOP_STOCKS = {
    "Semiconductor": ['NVDA', 'TSM', 'ASML', 'AMD', 'INTC', 'AVGO', 'QCOM', 'TXN', 'MU', 'ADI'],
    "AI": ['MSFT', 'GOOG', 'AMZN', 'META', 'ORCL', 'IBM', 'CRM', 'NOW', 'PATH', 'AI'],
    "Defense": ['LMT', 'RTX', 'BA', 'GD', 'NOC', 'HII', 'LHX', 'KBR', 'LDOS', 'BWXT']
}

# Mapping from ticker to company name
COMPANY_NAMES = {
    'NVDA': 'NVIDIA',
    'TSM': 'TSMC',
    'ASML': 'ASML',
    'AMD': 'AMD',
    'INTC': 'Intel',
    'AVGO': 'Broadcom',
    'QCOM': 'Qualcomm',
    'TXN': 'Texas Instruments',
    'MU': 'Micron Technology',
    'ADI': 'Analog Devices',
    'MSFT': 'Microsoft',
    'GOOG': 'Google',
    'AMZN': 'Amazon',
    'META': 'Meta',
    'ORCL': 'Oracle',
    'IBM': 'IBM',
    'CRM': 'Salesforce',
    'NOW': 'ServiceNow',
    'PATH': 'UiPath',
    'AI': 'C3.ai',
    'LMT': 'Lockheed Martin',
    'RTX': 'Raytheon Technologies',
    'BA': 'Boeing',
    'GD': 'General Dynamics',
    'NOC': 'Northrop Grumman',
    'HII': 'Huntington Ingalls Industries',
    'LHX': 'L3Harris Technologies',
    'KBR': 'KBR',
    'LDOS': 'Leidos',
    'BWXT': 'BWX Technologies'
}

# ========================
# FUNCTIONS
# ========================
def get_stock_data(ticker):
    """Fetch current stock data using Yahoo Finance"""
    stock = yf.Ticker(ticker)
    try:
        data = stock.history(period='1d')
        
        if data.empty:
            data = stock.history(period='5d').tail(1)
        
        if not data.empty:
            current_price = data['Close'][-1]
            previous_close = data['Close'][0] if len(data) > 1 else current_price
            daily_change = ((current_price - previous_close) / previous_close) * 100
            
            return {
                'symbol': ticker,
                'price': current_price,
                'daily_change': daily_change
            }
    except Exception as e:
        print(f"Error fetching stock data for {ticker}: {str(e)}")
    return None

def get_job_openings(company_name):
    """Get current job openings using SerpApi"""
    try:
        params = {
            "engine": "linkedin_jobs",
            "q": company_name,
            "location": "Worldwide",
            "api_key": SERPAPI_KEY
        }
        
        response = requests.get("https://serpapi.com/search", params=params)
        data = response.json()
        
        if "error" in data:
            print(f"SerpAPI error for {company_name}: {data['error']}")
            return 0
            
        # Get job count from API response
        if "jobs_results" in data:
            return len(data["jobs_results"])
        elif "search_parameters" in data:
            return data["search_parameters"].get("filters", {}).get("jobs_search_result_count", 0)
    except Exception as e:
        print(f"Error fetching jobs for {company_name}: {str(e)}")
    return 0

def load_references():
    """Load reference data from file"""
    if os.path.exists('references.json'):
        with open('references.json', 'r') as f:
            return json.load(f)
    return {
        'stock_references': {},
        'job_references': {},
        'last_report_date': None
    }

def save_references(references):
    """Save reference data to file"""
    with open('references.json', 'w') as f:
        json.dump(references, f)

def should_generate_job_report(references):
    """Determine if we should generate job report based on last run date"""
    if not references['last_report_date']:
        return True
        
    last_date = datetime.strptime(references['last_report_date'], "%Y-%m-%d")
    return (datetime.now() - last_date).days >= 10

def generate_report():
    """Generate performance report"""
    references = load_references()
    today = datetime.now().strftime("%Y-%m-%d")
    
    stock_report = {}
    job_report = {}
    new_references = False
    generate_jobs = should_generate_job_report(references)

    # Process stock data (always generated)
    for category, tickers in TOP_STOCKS.items():
        category_data = []
        
        for ticker in tickers:
            stock_data = get_stock_data(ticker)
            if not stock_data:
                continue
                
            current_price = stock_data['price']
            ref_key = f"{ticker}_reference"
            
            if ref_key not in references['stock_references']:
                references['stock_references'][ref_key] = current_price
                new_references = True
                
            ref_price = references['stock_references'][ref_key]
            ref_change = ((current_price - ref_price) / ref_price) * 100
            
            category_data.append({
                'Symbol': ticker,
                'Current Price': f"${current_price:.2f}",
                'Change vs Reference': f"{ref_change:+.2f}%",
                'Daily Change': f"{stock_data['daily_change']:+.2f}%"
            })
        
        stock_report[category] = pd.DataFrame(category_data)
    
    # Process job data (only every 10 days)
    job_data = []
    if generate_jobs:
        references['last_report_date'] = today
        new_references = True
        
        for category, tickers in TOP_STOCKS.items():
            for ticker in tickers:
                company_name = COMPANY_NAMES.get(ticker, ticker)
                current_jobs = get_job_openings(company_name)
                
                if ticker not in references['job_references']:
                    references['job_references'][ticker] = current_jobs
                    new_references = True
                    
                ref_jobs = references['job_references'][ticker]
                job_change = ((current_jobs - ref_jobs) / ref_jobs) * 100 if ref_jobs > 0 else 0
                
                job_data.append({
                    'Sector': category,
                    'Company': company_name,
                    'Current Jobs': current_jobs,
                    'Change vs Reference': f"{job_change:+.2f}%"
                })
                
                # Add delay to avoid rate limiting
                time.sleep(1)
    
    job_report = pd.DataFrame(job_data) if job_data else None
    
    if new_references:
        save_references(references)
    
    return stock_report, job_report, generate_jobs

def send_report(stock_report, job_report, has_job_data):
    """Send report via email"""
    today = datetime.now().strftime("%B %d, %Y")
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL
    
    # Adjust subject based on content
    if has_job_data:
        msg['Subject'] = f"10-Day Stock & Jobs Report - {today}"
    else:
        msg['Subject'] = f"Daily Stock Update - {today}"
    
    # Create HTML content
    html = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                h2 {{ color: #1a0dab; }}
                h3 {{ color: #174ea6; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th {{ background-color: #f2f2f2; text-align: left; padding: 12px; font-weight: bold; }}
                td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                tr:hover {{ background-color: #f5f5f5; }}
                .positive {{ color: green; font-weight: bold; }}
                .negative {{ color: red; font-weight: bold; }}
                .section {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .note {{ color: #666; font-size: 0.9em; margin-top: 20px; }}
                .info-banner {{ background-color: #e3f2fd; padding: 10px; border-radius: 5px; margin-bottom: 15px; }}
            </style>
        </head>
        <body>
            <h2>📊 {'10-Day' if has_job_data else 'Daily'} Investment Report ({today})</h2>
    """
    
    if has_job_data:
        html += """
            <div class="info-banner">
                💡 <strong>Comprehensive Report:</strong> Includes job market data (updated every 10 days)
            </div>
        """
    else:
        html += """
            <div class="info-banner">
                ⏳ <strong>Stock-Only Update:</strong> Job market data will refresh in next 10-day report
            </div>
        """
    
    html += """
            <div class="section">
                <h3>📈 Stock Performance Analysis</h3>
                <p>Reference prices are locked from initial run date. Daily changes show performance vs this reference.</p>
    """
    
    for category, df in stock_report.items():
        df['Change vs Reference'] = df['Change vs Reference'].apply(
            lambda x: f'<span class="{"positive" if "+" in x else "negative"}">{x}</span>')
        df['Daily Change'] = df['Daily Change'].apply(
            lambda x: f'<span class="{"positive" if "+" in x else "negative"}">{x}</span>')
        
        html += f"""
        <h4>🔧 {category} Sector</h4>
        {df.to_html(index=False, border=0, justify='left', escape=False)}
        <br>
        """
    
    html += """
            </div>
    """
    
    if has_job_data:
        html += """
            <div class="section">
                <h3>💼 Job Market Trends (10-Day Update)</h3>
                <p>Hiring activity as an indicator of company growth and investment potential</p>
        """
        
        # Format job report with sector grouping
        for sector in job_report['Sector'].unique():
            sector_jobs = job_report[job_report['Sector'] == sector]
            sector_jobs = sector_jobs.drop(columns=['Sector'])
            
            sector_jobs['Change vs Reference'] = sector_jobs['Change vs Reference'].apply(
                lambda x: f'<span class="{"positive" if "+" in x else "negative"}">{x}</span>')
            
            html += f"""
            <h4>👔 {sector} Sector Job Openings</h4>
            {sector_jobs.to_html(index=False, border=0, justify='left', escape=False)}
            <br>
            """
        
        html += """
            </div>
        """
    
    html += """
            <div class="note">
                <p><strong>Report Frequency:</strong></p>
                <ul>
                    <li>Stock data updated daily</li>
                    <li>Job market data updated every 10 days</li>
                    <li>Next comprehensive report: {next_report_date}</li>
                </ul>
                <p>Note: Job data from LinkedIn via SerpAPI | Stock data from Yahoo Finance</p>
            </div>
        </body>
    </html>
    """
    
    # Calculate next report date
    next_date = (datetime.now() + timedelta(days=10)).strftime("%B %d, %Y")
    html = html.replace("{next_report_date}", next_date)
    
    msg.attach(MIMEText(html, 'html'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print(f"Report email sent successfully! {'(With jobs)' if has_job_data else '(Stocks only)'}")
    except Exception as e:
        print(f"Error sending email: {str(e)}")

# ========================
# MAIN EXECUTION
# ========================
if __name__ == "__main__":
    # Install required packages
    try:
        import yfinance
        import pandas
        import requests
    except ImportError:
        import subprocess
        subprocess.run(["pip", "install", "yfinance", "pandas", "requests"])
    
    print("Generating investment report...")
    stock_report, job_report, has_job_data = generate_report()
    print("Sending email report...")
    send_report(stock_report, job_report, has_job_data)
    print("Process completed!")
