#!/usr/bin/env python  

"""The first step is to create an SMTP object, each object is used for connection 
with one server.

To send with Gmail follow the below instructions

Taken from http://stackoverflow.com/questions/10147455/trying-to-send-email-gmail-as-mail-provider-using-python
You need to enable less secure apps for gmail https://www.google.com/settings/security/lesssecureapps

However to send via Alopex mail server which requires no password follow these instructions
https://docs.python.org/2/library/email-examples.html
stackoverflow.com/questions/8856117/how-to-send-email-to-multiple-recipients-using-python-smtplib
"""

import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class Email:

	def __init__(self):

		self.Lidar = ['orfeo.colebatch@utoronto.ca',
		'bbyrne@physics.utoronto.ca',
		'dwunch@atmosp.physics.utoronto.ca',
		'jacob.hedelius@utoronto.ca',
		'astronasrin@gmail.com']
		#must be a list

		self.Orfeo = ['orfeo.colebatch@utoronto.ca'] 

	def send(self,
		Subject = "Testing sending using ALOPEX" ,\
		Body = "Testing sending mail using ALOPEX servers",\
		TO = "Lidar"):

		'''send email function, TO field must be a list'''

		try:			
			if TO == "Lidar":
				TO=self.Lidar
			elif TO == "Orfeo":
				TO=self.Orfeo

			else:
				print('TO recipient not understood')
			self.msg = MIMEText(str(Body))
			self.COMMASPACE = '; '
			self.msg['From'] = "taologbook@gmail.com"	
			self.msg['To'] = self.COMMASPACE.join(TO)
			#self.msg.preamble = 'test preamble from email_test.py'
			self.msg['Subject']= Subject

			s = smtplib.SMTP('mail.atmosp.physics.utoronto.ca')
			#s.sendmail(self.msg['From'], self.msg['To'], self.msg.as_string())
			s.sendmail(self.msg['From'], TO, self.msg.as_string())
			s.quit()
			print('Successfully sent email')
			return 1 # 1 = successful send
		except:
		    print("Failed to send email")
		    return 0 # 0 = failed send
