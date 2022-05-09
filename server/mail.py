import mailchimp_marketing as MailchimpMarketing
from mailchimp_marketing.api_client import ApiClientError

mailchimp = MailchimpMarketing.Client()
mailchimp.set_config({
  "api_key": "58a86f825a39e0767ce526d7bbdeae34-us10",
  "server": "us10"
})

body = {
  "permission_reminder": "You signed up for updates on our website",
  "email_type_option": False,
  "campaign_defaults": {
    "from_name": "Mailchimp",
    "from_email": "freddie@mailchimp.com",
    "subject": "Python Developers",
    "language": "EN_US"
  },
  "name": "JS Developers Meetup",
  "contact": {
    "company": "Mailchimp",
    "address1": "675 Ponce de Leon Ave NE",
    "address2": "Suite 5000",
    "city": "Atlanta",
    "state": "GA",
    "zip": "30308",
    "country": "US"
  }
}

try:
  response = mailchimp.lists.create_list(body)
  print("Response: {}".format(response))
except ApiClientError as error:
  print("An exception occurred: {}".format(error.text))