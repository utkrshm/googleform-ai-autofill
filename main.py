import argparse
import datetime
import json
import time
import requests
import random

from typing import List, Any, Union
from groq import Groq
import form

from dotenv import load_dotenv
load_dotenv()

client = Groq()

global personality, memory
personality = {"name": "none", "email_address": "na", "personality": "dne"}
memory = []

# PERSONALITY_MODEL = "openai/gpt-oss-20b"
PERSONALITY_MODEL = "openai/gpt-oss-120b"
RESPONSE_MODEL = "moonshotai/kimi-k2-instruct"
# RESPONSE_MODEL = "qwen/qwen3-32b"

def get_personality():
    prompt = """
Craft a unique personality about a person in college in India. Give them preferences about religion, following parent's advice, their behaviour, their characteristics, and give them some insecurities. Also give some viewpoints they might have on certain worldwide topics, like taste in music, and geopolitics and give them academic interests (if they exist) and creative characteristics (if they exist). Give me a detailed response of their personality, and only their personality.

Do not use the names: Rahul, Aryan, Arjun.

It is not necessary that this person be a good person, they can be a rebellious person as well.

Return your response as a JSON object:
{
    "name": "Name of the person (only the name, can also only be the first name)",
    "email_address": "Email address of the person, with a gmail account",
    "personality": "A full detailing of the person's personality, as a string"
}
    """
    
    return client.chat.completions.create(
        model=PERSONALITY_MODEL,
        messages=[ {"role": "user", "content": prompt} ],
        temperature=2,
        max_completion_tokens=8192,
        top_p=1,
        reasoning_effort="medium",
        stream=False,
        response_format={"type": "json_object"},
    ).choices[0].message
    
def get_response(question, choices: Union[List, str], required: bool):
    # Construct system prompt
    sys_prompt = f""" 
You are acting on behalf of a person as an intelligent agent to fill a google form. Your name is {personality['name']} with the email ID {personality['email_address']}. Your personality is this: \n {personality['personality']}.\n\nAct as this person and answer the questions posed to you in a formal manner, do not be informal with the responses.

If you have been given choices in a question, make sure that your response is a choice within the choices.

For open-ended questions, you may look at the personality of the person you're representing and write a low-effort (one word or max to max one line answers) or high-effort answer, talking like a real human being. If you don't want to answer it (if you think the person will not put too much effort into answering a form), you can just write "NA" or "-", in tune with the person's personality. Keep in mind that most people write very short answers to open-ended questions, only very few personalities type out good answers. You can also write "No" to a yes/no question.

These are the question answer pairs that have already been answered:\n
""" 
    for msg in memory:
        if msg['role'] == "user":
            sys_prompt += msg['content'] + " - "
        elif msg['role'] == 'assistant':
            sys_prompt += msg['content'] + "\n"
    sys_prompt += "\n\nYou have to return a JSON object with an \"response\" key."

    # Construct the user prompt
    usr_prompt = f"Question: {question}\n\n"
    if type(choices) == list:
        usr_prompt += f"Choices available to answer this question: {choices}"
    else:
        usr_prompt += f"This is a wide answer question so if you feel like it, you can leave it, or answer in one {choices}"
    if required:
        usr_prompt += "\n\nThis is a required question, so you must answer it. There's no option for you not to answer this question."
    
    retries = 0
    while True:    
        try:
            response = client.chat.completions.create(
                model=RESPONSE_MODEL,
                messages=[ 
                    {"role": "system", "content": sys_prompt}, 
                    {"role": "user", "content": usr_prompt} 
                ],
                temperature=2,
                max_completion_tokens=8192,
                top_p=1,
                stream=False,
                response_format={"type": "json_object"},
            ).choices[0].message.content   
            response = json.loads(response)['response']        # type: ignore
            
            if type(choices) == list and response in choices: break
            elif type(choices) == str: break
        except Exception as e:
            print(f"Failed to retrieve answer, retrying...\nError: {e}")
            retries += 1
            if retries == 3: raise Exception("Max retries for fetching answer exceeded...")
            continue


    memory.extend([
        { "role": "user", "content": usr_prompt },
        { "role": "assistant", "content": response }
    ])
    return response

def fill_agentic_answer(type_id, entry_id, options, required = False, entry_name = ''):
    ''' Use agentic AI to fill the responses to the form 
        Customize your own fill_algorithm here
        Note: please follow this func signature to use as fill_algorithm in form.get_form_submit_request '''
    
    # print(type_id, entry_id, options, required, entry_name)
    
    if "your name" in entry_name.lower():
        prob = random.randint(0, 100)
        return personality['name'] if prob > 50 else personality['name'].split()[0]
    
    # Send email only if required or if "mood strikes"
    if "email" in entry_name.lower():
        prob = random.randint(0, 100)
        if prob > 50 or required: return personality['email_address']
        else: return ""
    
    # # Don't answer not required questions, answer if "mood strikes"
    # if not required:
    #     prob = random.randint(0, 100)
    #     if prob > 50: return

    
    # if type_id == 0: # Short answer
    #     response = get_response(entry_name, choices='sentence', required=required)
    # if type_id == 1: # Paragraph
    #     response =  get_response(entry_name, choices='paragraph', required=required)
    if type_id == 2: # Multiple choice
        response =  get_response(entry_name, choices=options, required=required)
    if type_id == 5: # Linear scale
        response =  get_response(entry_name, choices=options, required=required)

    if type_id in [0, 1]: response = ""
    print(f"Question: {entry_name}\nRequired: {required}\nChoices: {options}\nResponse: {response}\n")
    
    # if type_id == 3: # Dropdown
    #     return random.choice(options)
    # if type_id == 4: # Checkboxes
    #     return random.sample(options, k=random.randint(1, len(options)))
    # if type_id == 7: # Grid choice
    #     return random.choice(options)
    if type_id == 9: # Date
        return datetime.date.today().strftime('%Y-%m-%d')
    if type_id == 10: # Time
        return datetime.datetime.now().strftime('%H:%M')
    
    return response or 'NA'

def generate_request_body(url: str, only_required = False):
    ''' Generate random request body data '''
    data = form.get_form_submit_request(
        url,
        only_required = only_required,
        fill_algorithm = fill_agentic_answer,
        output = "return",
        with_comment = False
    )
    data = json.loads(data)
    # you can also override some values here
    return data

def submit(url: str, data: Any):
    ''' Submit form to url with data '''
    url = form.get_form_response_url(url)
    print("Submitting to", url)
    print("Data:", data, flush = True)
   
    res = requests.post(url, data=data, timeout=5)
    if res.status_code != 200:
        print("Error! Can't submit form", res.status_code)

def main(url, only_required = False):
    try:
        payload = generate_request_body(url, only_required = only_required)
        print(payload)
        submit(url, payload)
        print("Done!!!")
    except Exception as e:
        print("Error!", e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Submit google form with custom data')
    parser.add_argument('url', help='Google Form URL')
    parser.add_argument("-r", "--required", action='store_true', help='If you only want to submit the required questions')
    parser.add_argument("-n", "--num", type=int, nargs=1, help="Number of responses you want", default=50)
    args = parser.parse_args()
    
    for i in range(args.num[0]):
        print(f"\n\n\n\n===========SUBMISSION {i+1}=============")

        # Fetch correct and proper personality
        retries = 0
        while True:
            try:
                personality = json.loads(get_personality().content)
                memory = []
                break
            except Exception as e:
                print(f"Personality creation failed, retrying...\nError: {e}")
                retries += 1
                if retries == 3: raise Exception("Max retries for fetching personality exceeded...")
                continue
                    
        print(f"Name: {personality['name']}\nEmail: {personality['email_address']}\nPersonality: {personality['personality']}\n\n")
        main(args.url, args.required)
        
        print("\n\nSleeping for 10 seconds to avoid rate limiting\n\n")
        time.sleep(10)
