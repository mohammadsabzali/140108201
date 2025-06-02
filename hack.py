from flask import Flask, render_template, request, send_file
import socket
import requests
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

app = Flask(__name__)

def get_ip(domain):
    try:
        return socket.gethostbyname(domain)
    except:
        return None

def get_status_and_title(domain):
    try:
        response = requests.get(f"http://{domain}", timeout=5)
        title = re.search(r"<title>(.*?)</title>", response.text, re.IGNORECASE)
        return {
            "status_code": response.status_code,
            "title": title.group(1) if title else "بدون عنوان"
        }
    except Exception as e:
        return {
            "status_code": "خطا",
            "title": str(e)
        }

def scan_ports(ip):
    open_ports = []
    ports_to_scan = [21, 22, 80, 443, 8080]

    for port in ports_to_scan:
        try:
            sock = socket.socket()
            sock.settimeout(0.5)
            sock.connect((ip, port))  # تلاش برای اتصال به پورت
            open_ports.append(port)  # اگر موفق شد، پورت بازه
            sock.close()
        except:
            continue  # اگر خطا داد، یعنی پورت بسته‌ست یا اتصال ممکن نیست
    return open_ports

def extract_info(domain):
    def try_fetch(url):
        try:
            response = requests.get(url, timeout=5)
            return response
        except:
            return None

    # امتحان http و https
    response = try_fetch(f"http://{domain}") or try_fetch(f"https://{domain}")

    if not response:
        return {
            "status": "خطا در اتصال",
            "emails": [],
            "phones": [],
            "title": None
        }

    content = response.text

    # استخراج ایمیل
    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", content)

    # استخراج شماره تلفن (فرمت‌های ایران و بین‌المللی)
    phones = re.findall(r"(?:\+98|0)?9\d{9}|\+?\d{1,4}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}", content)

    # استخراج عنوان
    title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else "بدون عنوان"

    return {
        "status": "موفق",
        "emails": list(set(emails)),
        "phones": list(set(phones)),
        "title": title
    }


def save_html_report(result):
    with open("report.html", "w", encoding="utf-8") as f:
        f.write(f"""
        <html>
        <head><meta charset='UTF-8'><title>گزارش امنیتی</title></head>
        <body style='font-family: Tahoma; direction: rtl; background-color: #f9f9f9; padding: 20px;'>
            <h2>گزارش اسکن برای {result['domain']}</h2>
            <p><strong>IP:</strong> {result['ip']}</p>
            <p><strong>Status Code:</strong> {result['status_code']}</p>
            <p><strong>Page title:</strong> {result['title']}</p>
            <p><strong>Open ports:</strong> {', '.join(str(p) for p in result['ports']) or 'ندارد'}</p>
            <p><strong>Emails found:</strong> {', '.join(result['emails']) or 'یافت نشد'}</p>
        </body>
        </html>
        """)

def send_report_via_email(to_email, report_path):
    from_email = "YOUR_EMAIL@gmail.com"
    app_password = "YOUR_APP_PASSWORD"
    subject = "گزارش اسکن امنیتی"

    with open(report_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_content, "html"))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(from_email, app_password)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"خطا در ارسال ایمیل: {e}")
        return False

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    if request.method == "POST":
        domain = request.form.get("domain")
        email = request.form.get("email")

        ip = get_ip(domain)
        status_title = get_status_and_title(domain)
        ports = scan_ports(ip) if ip else []
        emails = extract_info(domain)

        result = {
            "domain": domain,
            "ip": ip,
            "status_code": status_title["status_code"],
            "title": status_title["title"],
            "ports": ports,
            "emails": emails
        }

        save_html_report(result)

        if email:
            send_report_via_email(email, "report.html")

    return render_template("index.html", result=result)

@app.route("/download-report")
def download_report():
    report_path = "report.html"
    if os.path.exists(report_path):
        return send_file(report_path, as_attachment=True)
    else:
        return "گزارش موجود نیست.", 404

if __name__ == "__main__":
    app.run(debug=True)
