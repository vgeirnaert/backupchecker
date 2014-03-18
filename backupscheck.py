import xml.etree.ElementTree as ET
import sys
import os
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class CheckCondition:
	type = ""
	value = 0

# Check class, contains code that executes a specific check
class Check:
	location = ""
	name = ""
	conditions = [] # list of CheckCondition objects
	success = None
	summary = ""
	
	def run(self):
		if os.path.exists(self.location):
			# check all conditions
			for condition in self.conditions:
				if condition.type == "modifiedAge":
					modifiedAge = os.stat(self.location).st_mtime
					if (datetime.datetime.now() - datetime.datetime.fromtimestamp(modifiedAge)) < datetime.timedelta(hours=condition.value): 
						self.summary = "Passed"
						self.success = True
					else:
						self.summary = "File " + self.location + " is too old"
						self.success = False
						break
				elif condition.type == "minimumFileSize":
					fileSize = 0
					# check individual file size
					if(os.path.isfile(self.location)):
						fileSize = os.path.getsize(self.location)
					else: #check folder size
						fileSize = self.getFolderSize(self.location)
						
					if(fileSize < (condition.value * 1024 * 1024)): # value is in megabytes, but filesize is in bytes
						# we're smaller than the minimum size and fail the check
						self.summary = self.location + " has size " + str(round(fileSize / (1024 *1024), 2)) + "MB, minimum is " + str(condition.value) + "MB"
						self.success = False
						break
					else:
						self.summary = "Passed"
						self.success = True
						
				elif condition.type == "minimumFileCount":
					if(os.path.isfile(self.location)):
						# we can only count in folders, so this check fails
						self.summary = self.location + " is not a folder"
						self.success = False
						break
					else: 
						fileCount = self.getFileCount(self.location)
						
						if(fileCount < condition.value):
							self.summary = self.location + " contains " + str(fileCount) + " files, less than the specified minimum " + str(condition.value)
							self.success = False
							break
						else:
							self.summary = "Passed"
							self.success = True
				else:
					self.summary = "Unknown condition: " + condition.type
					self.success = False
					break
		else:
			self.success = False
			self.summary = self.location + " does not exist"
			
	def getFolderSize(self, start_path):
		total_size = 0
		for dirpath, dirnames, filenames in os.walk(start_path):
			for f in filenames:
				fp = os.path.join(dirpath, f)
				total_size += os.path.getsize(fp)
		return total_size
		
	def getFileCount(self, start_path):
		fileCount = 0
		for dirpath, dirnames, filenames in os.walk(start_path):
			fileCount = fileCount + len(filenames)

		return fileCount

# This class loads the settings file and makes the settings 
# available to the rest of the script
class Settings:
	email = ""
	smtp_server = ""
	smtp_username = ""
	smtp_password = ""
	smtp_port = ""
	smtp_email = ""
	checks = [] # list of Check objects
	
	# constructor
	def __init__(self, fileLocation):
		try:
			tree = ET.parse(fileLocation)
			root = tree.getroot()
			
			# reporting settings
			emailElement = root.find('Reporting/Email')
			if ET.iselement(emailElement):
				self.email = emailElement.text
			else:
				print("Error: unable to find email element in " + fileLocation)
				
			serverElement = root.find('Reporting/SmtpServer/Address')
			if ET.iselement(serverElement):
				self.smtp_server = serverElement.text
			else:
				print("Error: unable to find SMTP server address")
				
			usernameElement = root.find('Reporting/SmtpServer/Username')
			if ET.iselement(usernameElement):
				self.smtp_username = usernameElement.text
			else:
				print("Error: unable to find SMTP username")
				
			passwordElement = root.find('Reporting/SmtpServer/Password')
			if ET.iselement(passwordElement):
				self.smtp_password = passwordElement.text
			else:
				print("Error: unable to find SMTP password")
				
			portElement = root.find('Reporting/SmtpServer/Port')
			if ET.iselement(portElement):
				self.smtp_port = portElement.text
			else:
				print("Error: unable to find SMTP port")
				
			fromElement = root.find('Reporting/SmtpServer/Email')
			if ET.iselement(fromElement):
				self.smtp_email = fromElement.text
			else:
				print("Error: unable to find SMTP email")
				
			# checks
			for check in root.findall('Checks/Check'):
				myCheck = Check()
				myCheck.location = check.find('Location').text
				myCheck.name = check.find('Name').text
				
				myConditions = []
				
				# conditions
				for condition in check.findall('Conditions/Condition'):
					newCondition = CheckCondition()
					newCondition.type = condition.get('type')
					newCondition.value = int(condition.get('value'))
					myConditions.append(newCondition)
				
				myCheck.conditions = myConditions
				self.checks.append(myCheck)
				
		except ET.ParseError as e:
			print("Error parsing XML: {0}".format(e))
	
	def getEmail(self):
		return self.email
		
	def getChecks(self):
		return self.checks
		
	def getServerAddress(self):
		return self.smtp_server
		
	def getServerUsername(self):
		return self.smtp_username
		
	def getServerPassword(self):
		return self.smtp_password
		
	def getServerPort(self):
		return self.smtp_port
		
	def getServerEmail(self):
		return self.smtp_email
		
# This class executes the checks defined in the settings
class BackupsChecker:

	def run(self, fileLocation):
		summaries = [] # list of CheckSummary objects
		settings = Settings(fileLocation)
		
		checks = settings.getChecks()
		
		fails = 0
		
		for check in checks:
			check.run()
			summary = CheckSummary()
			summary.name = check.name
			summary.summary = check.summary
			summary.success = check.success
			
			if not summary.success:
				fails = fails + 1
				
			summaries.append(summary)
			
		self.report(summaries, settings, fails)
			
	def report(self, summaries, settings, fails):
		sender = settings.getServerEmail()
		
		failString = ""
		if fails > 0:
			failString = " (" + str(fails) + " failed)"
			
		msg = MIMEMultipart('alternative')
		msg['Subject'] = "Backup Integrity Report " + str(datetime.date.today()) + failString
		msg['From'] = sender
		msg['To'] = settings.getEmail()
		
		title = "Backup report from " + str(datetime.datetime.now())
		
		# format plain text email content
		summaryString = title + ":\n\n"
		for summary in summaries:
			myname = "[FAIL] " + summary.name
			if summary.success:
				myname = "[SUCCESS] " + summary.name
				
			summaryString = summaryString + myname + ": " + summary.summary + "\n" 
			
		part1 = MIMEText(summaryString, 'plain')
		msg.attach(part1)
		
		# format html email content
		summaryHtml = """\
			<html>
				<head>
				<style>
					body {
						font-family: arial;
					}

					td,th	{
						padding: 3px;
						padding-left: 1em;
						padding-right: 1em;
					}

					th {
						text-align: left;
					}

					tr.FAILED {
						background-color:#FF6666;
					}

					tr.PASSED {
						background-color: #85E085;
					}
					</style>
				</head>
				<body>
					<h1>""" + title + """</h1>
					<h2>""" + str(len(summaries) - fails) + """ checks passed, """ + str(fails) + """ failed</h2>
					<table>
						<tr>
							<th>Status</th><th>Check</th><th>Comment</th>
						</tr>"""
		for summary in summaries:
			success = "FAILED"
			if summary.success:
				success = "PASSED"
				
			summaryHtml = summaryHtml + "<tr class=\"" + success + "\"><td>" + success + "</td><td>" + summary.name + "</td><td>" + summary.summary + "</td></tr>"
			
		summaryHtml = summaryHtml + """
					</table>
				</body>
			</html>
		"""
		
		part2 = MIMEText(summaryHtml, 'html')
		msg.attach(part2)
		
		# send mail
		try:
			print('connecting to ' + settings.getServerAddress())
			s = smtplib.SMTP(settings.getServerAddress(), settings.getServerPort())
			print(s.ehlo())
			print(s.starttls())
			s.login(settings.getServerUsername(), settings.getServerPassword())
			try:
				s.sendmail(sender, settings.getEmail(), msg.as_string())
			except Exception as e:
				print("Unable to send mail: " + str(e))
			finally:
				s.quit
		except Exception as e:
			print("Unable to connect to SMTP: " + str(e))
	
class CheckSummary:
	name = ""
	summary = ""
	success = False
	
# script starts here:

# check if we have an argument
if len(sys.argv) == 2:
	checker = BackupsChecker()
	checker.run(sys.argv[1])
else:
	print("Error: missing settings file location!")