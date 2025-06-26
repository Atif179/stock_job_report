import yfinance as yf
import pandas as pd
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import json
import os
import time

# ========================
# CONFIGURATION
# ========================
SENDER_EMAIL = os.environ.get('SENDER_EMAIL')
SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD')
RECIPIENT_EMAIL = os.environ.get('RECIPIENT_EMAIL')

# Define top stocks in each category (ticker symbols)
TOP_STOCKS = {
    "Semiconductor": ['NVDA', 'TSM', 'ASML', 'AMD', 'INTC', 'AVGO', 'QCOM', 'TXN', 'MU', 'ADI'],
    "AI": ['MSFT', 'GOOG', 'AMZN', 'META', 'ORCL', 'IBM', 'CRM', 'NOW', 'PATH', 'AI'],
    "Defense": ['LMT', 'RTX', 'BA', 'GD', 'NOC', 'HII', 'LHX', 'KBR', 'LDOS', 'BWXT']
}

# Mapping from ticker to company name for job search
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
        # Get today's data
        data = stock.history(period='1d')
        
        if data.empty:
            # Try getting last available data if today is holiday
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
    """Get current job openings using LinkedIn proxy"""
    try:
        # Use a proxy service to get job count
        response = requests.get(
            f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=&location=Worldwide&f_C={company_name}&trk=public_jobs_jobs-search-bar_search-submit",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )
        
        if response.status_code == 200:
            # Count the number of job listings
            job_count = response.text.count('job-card-container')
            return job_count
        else:
            print(f"Error fetching jobs for {company_name}: Status {response.status_code}")
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
        'job_references': {}
    }

def save_references(references):
    """Save reference data to file"""
    with open('references.json', 'w') as f:
        json.dump(references, f)

def generate_stock_report():
    """Generate stock performance report"""
    references = load_references()
    today = datetime.now().strftime("%Y-%m-%d")
    
    stock_report = {}
    job_report = {}
    new_references = False

    # Process stock data
    for category, tickers in TOP_STOCKS.items():
        category_data = []
        
        for ticker in tickers:
            stock_data = get_stock_data(ticker)
            if not stock_data:
                continue
                
            current_price = stock_data['price']
            ref_key = f"{ticker}_reference"
            
            # Set reference price if first run or not exists
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
        
        # Create DataFrame for the category
        stock_report[category] = pd.DataFrame(category_data)
    
    # Process job data
    all_tickers = [ticker for sublist in TOP_STOCKS.values() for ticker in sublist]
    job_data = []
    
    for ticker in all_tickers:
        company_name = COMPANY_NAMES.get(ticker, ticker)
        current_jobs = get_job_openings(company_name)
        
        # Set reference job count if first run or not exists
        if ticker not in references['job_references']:
            references['job_references'][ticker] = current_jobs
            new_references = True
            
        ref_jobs = references['job_references'][ticker]
        job_change = ((current_jobs - ref_jobs) / ref_jobs) * 100 if ref_jobs > 0 else 0
        
        job_data.append({
            'Company': company_name,
            'Current Jobs': current_jobs,
            'Change vs Reference': f"{job_change:+.2f}%"
        })
        
        # Add delay to avoid rate limiting
        time.sleep(2)
    
    job_report = pd.DataFrame(job_data)
    
    # Save updated references if new data
    if new_references:
        save_references(references)
    
    return stock_report, job_report

def send_stock_report(stock_report, job_report):
    """Send stock report via email"""
    today = datetime.now().strftime("%B %d, %Y")
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = f"Daily Stock & Jobs Report - {today}"
    
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
            </style>
        </head>
        <body>
            <h2>📊 Daily Stock & Job Market Report ({today})</h2>
            <p>Track investment opportunities through stock performance and hiring trends</p>
            
            <div class="section">
                <h3>📈 Stock Performance Analysis</h3>
                <p>Reference prices are locked from initial run date. Daily changes show performance vs this reference.</p>
    """
    
    for category, df in stock_report.items():
        # Format percentage changes with color coding
        df['Change vs Reference'] = df['Change vs Reference'].apply(
            lambda x: f'<span class="{"positive" if "+" in x else "negative"}">{x}</span>')
        df['Daily Change'] = df['Daily Change'].apply(
            lambda x: f'<span class="{"positive" if "+" in x else "negative"}">{x}</span>')
        
        html += f"""
        <h4>🔧 {category} Sector (Top 10)</h4>
        {df.to_html(index=False, border=0, justify='left', escape=False)}
        <br>
        """
    
    html += """
            </div>
            
            <div class="section">
                <h3>💼 Job Market Trends</h3>
                <p>Tracking hiring activity as an indicator of company growth and investment potential</p>
    """
    
    # Format job percentage changes
    job_report['Change vs Reference'] = job_report['Change vs Reference'].apply(
        lambda x: f'<span class="{"positive" if "+" in x else "negative"}">{x}</span>')
    
    html += f"""
        <h4>👔 Current Job Openings Analysis</h4>
        {job_report.to_html(index=False, border=0, justify='left', escape=False)}
        <br>
    """
    
    html += """
            </div>
            
            <div class="note">
                <p><strong>Analysis Insights:</strong></p>
                <ul>
                    <li>Stock reference prices are set on the first run and maintained for comparison</li>
                    <li>Job counts are worldwide openings scraped from LinkedIn</li>
                    <li>Increasing job openings often indicate company growth and expansion</li>
                    <li>Consistent job growth combined with stock performance may signal strong investment opportunities</li>
                </ul>
                <p>Note: Job data from LinkedIn | Stock data from Yahoo Finance | Reference values set on first run</p>
            </div>
        </body>
    </html>
    """
    
    msg.attach(MIMEText(html, 'html'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print("Stock and jobs report email sent successfully!")
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
    except ImportError:
        import subprocess
        subprocess.run(["pip", "install", "yfinance", "pandas", "requests"])
    
    print("Generating stock and job report...")
    stock_report, job_report = generate_stock_report()
    print("Sending email report...")
    send_stock_report(stock_report, job_report)
    print("Process completed!")
