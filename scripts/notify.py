import json, os, smtplib, ssl, sys, urllib.request
from email.message import EmailMessage

def notify(subject:str, message:str, level:str="error"):
    delivered=[]; errors=[]
    webhook=os.getenv("BACKUP_ALERT_WEBHOOK_URL","").strip()
    if webhook:
        try:
            body=json.dumps({"text":f"[{level.upper()}] {subject}\n{message}","subject":subject,"level":level}).encode()
            req=urllib.request.Request(webhook,data=body,headers={"Content-Type":"application/json"},method="POST")
            with urllib.request.urlopen(req,timeout=10) as res:
                if res.status >= 300: raise RuntimeError(f"HTTP {res.status}")
            delivered.append("webhook")
        except Exception as e: errors.append(f"webhook: {e}")
    host=os.getenv("SMTP_HOST","").strip(); recipient=os.getenv("BACKUP_ALERT_EMAIL_TO","").strip()
    if host and recipient:
        try:
            port=int(os.getenv("SMTP_PORT","587")); user=os.getenv("SMTP_USERNAME",""); password=os.getenv("SMTP_PASSWORD","")
            sender=os.getenv("BACKUP_ALERT_EMAIL_FROM",user or "quickboard@localhost")
            msg=EmailMessage(); msg["Subject"]=subject; msg["From"]=sender; msg["To"]=recipient; msg.set_content(message)
            if os.getenv("SMTP_SSL","false").lower()=="true":
                server=smtplib.SMTP_SSL(host,port,timeout=10,context=ssl.create_default_context())
            else:
                server=smtplib.SMTP(host,port,timeout=10); server.ehlo()
                if os.getenv("SMTP_STARTTLS","true").lower()=="true": server.starttls(context=ssl.create_default_context()); server.ehlo()
            if user: server.login(user,password)
            server.send_message(msg); server.quit(); delivered.append("email")
        except Exception as e: errors.append(f"email: {e}")
    print(json.dumps({"delivered":delivered,"errors":errors},ensure_ascii=False))
    return bool(delivered),errors

if __name__=="__main__":
    ok,errs=notify(sys.argv[1],sys.argv[2],sys.argv[3] if len(sys.argv)>3 else "error")
    raise SystemExit(0 if ok or not errs else 1)
