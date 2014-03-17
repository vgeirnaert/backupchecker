import xml.etree.ElementTree as ET
import sys
import os
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class CheckCondition:
	type = ""
	value = ""

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
					if (datetime.datetime.now() - datetime.datetime.fromtimestamp(modifiedAge)) < datetime.timedelta(hours=int(condition.value)): 
						self.summary = "Success"
						self.success = True
					else:
						self.summary = "File " + self.location + " is too old"
						self.success = False
						break;
				else:
					self.summary = "Unknown condition: " + condition.type
					self.success = False
					break
		else:
			self.success = False
			self.summary = self.location + " does not exist"

# This class loads the settings file and makes the settings 
# available to the rest of the script
class Settings:
	email = ""
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
					newCondition.value = condition.get('value')
					myConditions.append(newCondition)
				
				myCheck.conditions = myConditions
				self.checks.append(myCheck)
				
		except ET.ParseError as e:
			print("Error parsing XML: {0}".format(e))
	
	def getEmail(self):
		return self.email
		
	def getChecks(self):
		return self.checks
		
# This class executes the checks defined in the settings
class BackupsChecker:

	def run(self, fileLocation):
		summaries = [] # list of CheckSummary objects
		settings = Settings(fileLocation)
		
		checks = settings.getChecks()
		
		for check in checks:
			check.run()
			summary = CheckSummary()
			summary.name = check.name
			summary.summary = check.summary
			summary.success = check.success
			summaries.append(summary)
			
		self.report(summaries, settings)
			
	def report(self, summaries, settings):
		sender = 'backupscript@nomadsagency.com'
		msg = MIMEMultipart('alternative')
		msg['Subject'] = "Backup Integrity Report " + str(datetime.date.today())
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
				<head></head>
				<body>
					<h1>""" + title + """</h1>
					<table>
						<tr>
							<th>Status</th><th>Job</th><th>Comment</th>
						</tr>"""
		for summary in summaries:
			success = "FAILED"
			if summary.success:
				success = "SUCCESS"
				
			summaryHtml = summaryHtml + "<tr class=\"" + success + "\"><td>" + success + "</td><td>" + summary.name + "</td><td>" + summary.summary + "</td></tr>"
			
		summaryHtml = summaryHtml + """
					</table>
				</body>
			</html>
		"""
		
		part2 = MIMEText(summaryHtml, 'html')
		msg.attach(part2)
		
		# send mail
		s = smtplib.SMTP('localhost')
		s.sendmail(sender, settings.getEmail(), msg.as_string())
		s.quit
	
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