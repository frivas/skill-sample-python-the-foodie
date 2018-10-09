# -*- coding: utf-8 -*-

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import (
	AbstractRequestHandler, AbstractExceptionHandler)
from ask_sdk_core import attributes_manager
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import (
	Response, request_envelope, Slot, SlotConfirmationStatus, DialogState)
from ask_sdk_model.ui import SimpleCard
from ask_sdk_model.ui import AskForPermissionsConsentCard
from ask_sdk_model.slu.entityresolution import StatusCode
from ask_sdk_model.dialog import DelegateDirective, ElicitSlotDirective

import logging
import six
import requests
import random
import json


sb = SkillBuilder()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# CONSTANTS
permissions = ['read::alexa:device:all:address']

requiredSlots = {
	"allergies": True,
	"meal": True,
	"cuisine": True,
	"diet": True,
	"deliveryOption": True,
	"timeOfDay": True
}


class LaunchRequestHandler(AbstractRequestHandler):

	def can_handle(self, handler_input):
		return is_request_type("LaunchRequest")(handler_input)
	
	def handle(self, handler_input):
		logger.info("In LaunchRequestHandler")
		attributesManager = handler_input.attributes_manager
		sessionAttributes = attributesManager.session_attributes
		logger.info(sessionAttributes)
		speechText = getWelcomeMessage(sessionAttributes) + " " + getPrompt(sessionAttributes)

		return handler_input.response_builder.speak(speechText).ask(speechText).set_card(AskForPermissionsConsentCard(permissions)).response

class LaunchRequestWithConsentTokenHandler(AbstractRequestHandler):
	def can_handle(self, handler_input):
		return (
	is_request_type("LaunchRequest")(handler_input) 
	and keysExists(handler_input.request_envelope, "context", "System", "user", "permissions") 
	and keysExists(handler_input.request_envelope, "context", "System", "user", "permissions", "consentToken")
		)
	
	def handle(self, handler_input):
		logger.info("In LaunchRequestWithConsentTokenHandler")
		attributesManager = handler_input.attributes_manager
		sessionAttributes = attributesManager.session_attributes
		logger.info(sessionAttributes)
		speechText = getWelcomeMessage(sessionAttributes) + " " + getPrompt(sessionAttributes)

		return handler_input.response_builder.speak(speechText).ask(speechText).response

class SIPRecommendationIntentHandler(AbstractRequestHandler):
	def can_handle(self, handler_input):
		return (is_intent_name("RecommendationIntent")(handler_input) and
		handler_input.request_envelope.request.dialog_state != DialogState.COMPLETED)

	def handle(self, handler_input):
		currentIntent = handler_input.request_envelope.request.intent
		
		result = disambiguateSlot(getSlotValues(currentIntent.slots))

		if result:
			handler_input.response_builder.speak(result["prompt"]).ask(result["prompt"]).add_directive(ElicitSlotDirective(slot_to_elicit=result["slotName"])).response
		else:
			handler_input.response_builder.add_directive(DelegateDirective(updated_intent=currentIntent)).response

		return handler_input.response_builder.response

class CancelAndStopIntentHandler(AbstractRequestHandler):

	def can_handle(self, handler_input):
		return is_intent_name("AMAZON.CancelIntent")(handler_input) or is_intent_name("AMAZON.SetopIntent")(handler_input)
	
	def handle(self, handler_input):
		speechText = "Goodbye!"

		return handler_input.response_builder.speak(speechText).set_card(SimpleCard("The Foodie", speechText)).response

def getWelcomeMessage(sessionAttributes):
	speechText = ""
	
	if sessionAttributes:
		speechText = (
			"<say-as interpret-as=\"interjection\">Howdy!</say-as> "
			"Welcome to The Foodie! "
			"I'll help you find the right food right now. "
			"To make that easier, you can give me permission to access your location, "
			"just check the Alexa app. "
			)
	else:
		speechText += "Welcome back!! "

		timeOfDay = sessionAttributes.get("timeOfDay","")

		if timeOfDay:
			speechText += getTimeOfDayMessage(timeOfDay)
		else:
			speechText += "It's time to stuff your face with delicious food. "
		
		if keysExists(sessionAttributes,"recommendations", "previous","meal"):
			speechText += "It looks like last time you had " + sessionAttributes["recommendations"]["previous"]["meal"] + ". "
			speechText += "I wonder what it will be today. "

	return speechText	

def getPrompt(sessionAttributes):
	speechText = "How rude of me. I forgot to ask. What's your name?"
	
	if not sessionAttributes:
		speechText = (
			"Let's narrow it down. What flavors do you feel like?"
			"You can say things like spicy, savory, greasy, and fresh."
		)
	
	return speechText

def getTimeOfDayMessage(timeOfDay):
	messages = timeOfDayMessages[timeOfDay]
	return randomPhrase(messages)

def randomPhrase(phraseList):
	return random.choice(phraseList)

timeOfDayMessages = {
  "breakfast": [
	"It looks like it's breakfast. ",
	"<say-as interpret-as=\"interjection\">cock a doodle doo</say-as> It's time for breakfast. ", 
	"Good morning! Time for breakfast"
  ],
  "brunch": [
	"<say-as interpret-as=\"interjection\">cock a doodle doo</say-as> Let's get some brunch! ", 
	"It's time for brunch. "
  ],
  "lunch": [
	"Lunch time! ",
	"Time for lunch. "
  ],
  "dinner": [
	"It's dinner time. ",
	"It's supper time. "
  ],
  "midnight": [
	"<say-as interpret-as=\"interjection\">wowza</say-as> You're up late! You looking for a midnight snack? ",
	"It's time for a midnight snack. "
  ]
}

# Dictionary Helper
def keysExists(element, *keys):
	'''
	Check if *keys (nested) exists in `element` (dict).
	'''
	if type(element) is not dict:
		raise AttributeError('keysExists() expects dict as first argument.')
	if len(keys) == 0:
		raise AttributeError('keysExists() expects at least two arguments, one given.')

	_element = element
	for key in keys:
		try:
			_element = _element[key]
		except KeyError:
			return False
	return True

def getSlotValues(filled_slots):
	# """Return slot values with additional info."""
	# # type: (Dict[str, Slot]) -> Dict[str, Any]
	slot_values = {}
	
	for _ , slot_item in six.iteritems(filled_slots):
		name = slot_item.name
		
		if slot_item.resolutions:
			status_code = slot_item.resolutions.resolutions_per_authority[0].status.code

			if status_code == StatusCode.ER_SUCCESS_MATCH:
				valuesList = slot_item.resolutions.resolutions_per_authority[0].values

				slot_values[name] = {
					"synonym": slot_item.value,
					"resolved": [aDict.value.name for aDict in valuesList] if valuesList != 'None' else [],
					"is_validated": True,
				}
			elif status_code == StatusCode.ER_SUCCESS_NO_MATCH:
				slot_values[name] = {
					"synonym": slot_item.value,
					"resolved": slot_item.value if slot_item.value else [],
					"is_validated": False,
				}
			else:
				pass
		else:
			slot_values[name] = {
				"synonym": slot_item.value,
				"resolved": slot_item.value,
				"is_validated": False,
			}

	return slot_values

def disambiguateSlot(slots):
	result = {}

	for key, slot_item in six.iteritems(slots):
		if isinstance(slot_item["resolved"], list) and len(slot_item['resolved']) > 1 and requiredSlots[key]:
			result = {
				"slotName": key,
				"prompt": 'Which one would you like ' + ' or '.join(slot_item["resolved"]) + '?'
			}

	return result

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(LaunchRequestWithConsentTokenHandler())
sb.add_request_handler(SIPRecommendationIntentHandler())
#sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelAndStopIntentHandler())
#sb.add_request_handler(SessionEndedRequestHandler())

#sb.add_exception_handler(AllExceptionHandler())

handler = sb.lambda_handler()