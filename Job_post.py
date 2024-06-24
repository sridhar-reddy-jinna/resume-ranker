from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from flask import Blueprint, render_template, request, url_for, redirect, session, jsonify
from werkzeug.utils import secure_filename
import os,fitz
from bson.objectid import ObjectId
import docx2txt
from database import mongo
from datetime import datetime
from Matching import Matching


job_post = Blueprint("Job_post", __name__, static_folder="static", template_folder="templates")


UF = "static/Job_Description"
JOBS = mongo.db.JOBS
Applied_EMP = mongo.db.Applied_EMP
resumeFetchedData = mongo.db.resumeFetchedData
IRS_USERS = mongo.db.IRS_USERS
def allowedExtension(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ['docx','pdf']

def extractData(file,ext):
    text=""
    if ext=="docx": 
        temp = docx2txt.process(file)
        text = [line.replace('\t', ' ') for line in temp.split('\n') if line]
        text = ' '.join(text)
    if ext=="pdf":
        for page in fitz.open(file):
            text = text + str(page.get_text())
        text = " ".join(text.split('\n'))
    return text
@job_post.route("/")
def home():
    return "<h1>test</h1>"

@job_post.route("/post_job")
def JOB_POST():
    fetched_jobs = None
    fetched_jobs = JOBS.find({},{"_id":1,"Job_Profile":1,"CompanyName":1,"CreatedAt":1,"Job_description_file_name":1,"LastDate":1,"Salary":1}).sort([("CreatedAt",-1)])
    if fetched_jobs == None:
        return render_template("job_post.html",errorMsg="Problem in Jobs Fetched")
    else:
        jobs={}
        cnt = 0
        for i in fetched_jobs: 
            jobs[cnt] = {"job_id":i['_id'],"Job_Profile":i['Job_Profile'],"CompanyName":i['CompanyName'],"CreatedAt":i['CreatedAt'],"Job_description_file_name":i['Job_description_file_name'],'LastDate':i['LastDate'],"Salary":i['Salary'] }
            cnt += 1
        return render_template("job_post.html",len = len(jobs), data = jobs)

@job_post.route("/add_job", methods=["POST"])
def ADD_JOB():
    try:
        print("Uploading JD")
        file = request.files['jd']
        job_profile = str(request.form.get('jp'))
        company = str(request.form.get('company'))
        last_date = str(request.form.get('last_date'))
        salary = str(request.form.get('salary'))
        filename = secure_filename(file.filename)
        jd_id = ObjectId()
        path = os.path.join(UF,str(jd_id))
        os.mkdir(path)

        file.save(os.path.join(path, filename))
        fetchedData = extractData(path+"/"+filename,file.filename.rsplit('.',1)[1].lower())
        print("Jd Uploaded")



        result = None     
        result = JOBS.insert_one({"_id":jd_id,"Job_Profile":job_profile,"Job_Description":fetchedData,"CompanyName":company,"LastDate":last_date,"CreatedAt":datetime.now(),"Job_description_file_name":filename,"Salary":salary})
        with open(os.path.join(path, filename), "rb") as f:
            jd_data = f.read()

        JOBS.update_one({"_id": jd_id}, {"$set": {"FileData": jd_data}})
        print("JD added to Database")
        
        if result == None:
            return render_template("job_post.html",errorMsg="Error Ocuured")
        else:
            return redirect('/HR1/post_job')
            
    except Exception:
        print("Exception Occured 123")

@job_post.route("/show_job")
def show_job():
    company = request.cookies.get('tcs')
    fetched_jobs = None
    fetched_jobs = JOBS.find({},{"_id":1,"Job_Profile":1,"CompanyName":1,"CreatedAt":1,"Job_description_file_name":1,"LastDate":1,"Salary":1}).sort([("CreatedAt",-1)])
    if fetched_jobs == None:
        return render_template("All_jobs.html",errorMsg="Problem in Jobs Fetched")
    else:
        jobs={}
        cnt = 0
        
        for i in fetched_jobs:
            jobs[cnt] = {"job_id":i['_id'],"Job_Profile":i['Job_Profile'],"CompanyName":i['CompanyName'],"CreatedAt":i['CreatedAt'],"Job_description_file_name":i['Job_description_file_name'],'LastDate':i['LastDate'],"Salary":i['Salary']}
            cnt += 1
        return render_template("All_jobs.html",len = len(jobs), data = jobs, company = company)

@job_post.route("/apply_job",methods=["POST"])
def APPLY_JOB():
    job_id = request.form['job_id'] 
    match_percentage= Matching()
    result = None
    result = Applied_EMP.insert_one({"job_id":ObjectId(job_id),"user_id":ObjectId(session['user_id']),"User_name":session['user_name'],"Matching_percentage":match_percentage})
    if result == None:
        return jsonify({"StatusCode":400,"Message":"Problem in Applying"})
    return jsonify({"StatusCode":200,"Message":"Applied Successfully"})

@job_post.route("/view_applied_candidates",methods=["POST","GET"])
def view_applied_candidates():
    job_id = request.form['job_id']
    result_data = None
    result_data = Applied_EMP.find({"job_id":ObjectId(job_id)},{"User_name":1,"Matching_percentage":1,"user_id": 1}).sort([("Matching_percentage",-1)])
    if result_data == None:
        return {"StatusCode":400,"Message":"Problem in Fetching"}
    else:        
        result = {}
        cnt = 0
        result[0]=cnt
        result[1]=200
        for i in result_data:
           if i['Matching_percentage'] >= 50:  # Filter candidates with match percentage >= 50
                result[cnt + 2] = {"Name": i['User_name'], "Match": i['Matching_percentage']}
                cnt += 1  
        result[0]=cnt
        print("Result",result,type(result))
        return result
    

@job_post.route("/delete_job", methods=["POST"])
def DELETE_JOB():
    try:
        job_id = request.form['job_id']  # Get the job ID from the request
        
        # Delete the job post document from the MongoDB collection
        result = JOBS.delete_one({"_id": ObjectId(job_id)})
        
        if result.deleted_count == 1:
            return jsonify({"StatusCode": 200, "Message": "Job post deleted successfully"})
        else:
            return jsonify({"StatusCode": 404, "Message": "Job post not found or already deleted"})
    
    except Exception as e:
        print("Exception occurred:", str(e))
        return jsonify({"StatusCode": 500, "Message": "Internal server error"})

@job_post.route("/send_email_top5", methods=['POST'])
def send_email_top5():
    emails = request.form.getlist('emails[]')
    if not emails:
        return jsonify({'error': 'No emails provided'}), 400

    # Example usage of send_email function
    # for email in emails:
    #     send_email(email, "Subject", "Message")  # You need to define the send_email function
    # receiver_email = emails[0].strip('[]')
    # send_email(receiver_email, "Subject", "Message")
    for email in emails:
        receiver_email = email.strip('[]')
        send_email(receiver_email, "Subject", "Message")

    print(emails[0])
    return jsonify({'message': 'Emails sent successfully'}), 200

#new code
def send_email(receiver_email, subject, message):
    
    smtp_server = "smtp.gmail.com"
    smtp_port = 587  

    
    sender_email = "sridharreddyjinna.18@gmail.com"
    password = "eedwplmsdtmmhazx"

    subject = "Greetings from Resume Screener"
    message = "Congratulations, You have been Shortlisted to Further process"
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(message, 'plain'))
    print(receiver_email)

    try:
        # Connect to SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, password)

        # Send email
        server.sendmail(sender_email, receiver_email, msg.as_string())
        print(f"Email sent successfully to {receiver_email}")

    except Exception as e:
        print(f"Error sending email to {receiver_email}: {str(e)}")

    finally:
        # Close the SMTP server connection
        server.quit() if 'server' in locals() else None
