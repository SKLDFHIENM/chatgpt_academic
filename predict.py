# 借鉴了 https://github.com/GaiZhenbiao/ChuanhuChatGPT 项目

import json
import gradio as gr
import logging
import traceback
import requests
import importlib
from typing import Dict, List, Tuple, Generator, Any, Optional, Union

# Configuration loading
def load_api_config():
    """Load API configuration from private config if available, otherwise from public config"""
    try:
        from config_private import proxies, API_URL, API_KEY, TIMEOUT_SECONDS, MAX_RETRY, LLM_MODEL
    except ImportError:
        from config import proxies, API_URL, API_KEY, TIMEOUT_SECONDS, MAX_RETRY, LLM_MODEL
    
    return {
        'proxies': proxies,
        'api_url': API_URL,
        'api_key': API_KEY,
        'timeout': TIMEOUT_SECONDS,
        'max_retry': MAX_RETRY,
        'model': LLM_MODEL
    }

# Constants
TIMEOUT_BOT_MSG = '[local] Request timeout, network error. please check proxy settings in config.py.'

# Load configuration
API_CONFIG = load_api_config()

def get_full_error(chunk: bytes, stream_response: Generator) -> bytes:
    """Collect all remaining chunks from a stream to get the full error message"""
    while True:
        try:
            chunk += next(stream_response)
        except (StopIteration, Exception):
            break
    return chunk

def generate_payload(
    inputs: str,
    top_p: float,
    temperature: float,
    history: List[str],
    system_prompt: str,
    stream: bool
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """Generate API request headers and payload"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_CONFIG['api_key']}"
    }

    conversation_cnt = len(history) // 2

    # Start with system message
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history
    if conversation_cnt:
        for index in range(0, 2*conversation_cnt, 2):
            user_message = {"role": "user", "content": history[index]}
            assistant_message = {"role": "assistant", "content": history[index+1]}
            
            # Skip empty or timeout messages
            if user_message["content"] != "":
                if assistant_message["content"] == "": 
                    continue
                if assistant_message["content"] == TIMEOUT_BOT_MSG: 
                    continue
                messages.append(user_message)
                messages.append(assistant_message)
            else:
                # Handle case where user message is empty but assistant message exists
                messages[-1]['content'] = assistant_message['content']

    # Add current user input
    messages.append({"role": "user", "content": inputs})

    # Create payload
    payload = {
        "model": API_CONFIG['model'],
        "messages": messages, 
        "temperature": temperature,
        "top_p": top_p,
        "n": 1,
        "stream": stream,
        "presence_penalty": 0,
        "frequency_penalty": 0,
    }
    
    print(f" {API_CONFIG['model']} : {conversation_cnt} : {inputs}")
    return headers, payload

def predict_no_ui(
    inputs: str,
    top_p: float,
    temperature: float,
    history: List[str] = []
) -> str:
    """Make a prediction without UI updates (non-streaming)"""
    headers, payload = generate_payload(
        inputs, top_p, temperature, history, system_prompt="", stream=False
    )

    retry = 0
    while True:
        try:
            # Make a POST request to the API endpoint, stream=False
            response = requests.post(
                API_CONFIG['api_url'],
                headers=headers,
                proxies=API_CONFIG['proxies'],
                json=payload,
                stream=False,
                timeout=API_CONFIG['timeout'] * 2
            )
            break
        except requests.exceptions.ReadTimeout:
            retry += 1
            traceback.print_exc()
            if API_CONFIG['max_retry'] != 0:
                print(f'请求超时，正在重试 ({retry}/{API_CONFIG["max_retry"]}) ……')
            if retry > API_CONFIG['max_retry']:
                raise TimeoutError("Maximum retry attempts exceeded")

    try:
        result = json.loads(response.text)["choices"][0]["message"]["content"]
        return result
    except Exception:
        if "choices" not in response.text:
            print(response.text)
        raise ConnectionAbortedError("Json解析不合常规，可能是文本过长" + response.text)

def predict(
    inputs: str,
    top_p: float,
    temperature: float,
    chatbot: List[Tuple[str, str]] = [],
    history: List[str] = [],
    system_prompt: str = '',
    stream: bool = True,
    additional_fn: Optional[str] = None
) -> Generator[Tuple[List[Tuple[str, str]], List[str], str], None, None]:
    """Make a prediction with UI updates (streaming)"""
    # Apply additional function if specified
    if additional_fn is not None:
        import functional
        importlib.reload(functional)
        functional_modules = functional.get_functionals()
        inputs = functional_modules[additional_fn]["Prefix"] + inputs + functional_modules[additional_fn]["Suffix"]

    # Initial UI update for streaming mode
    if stream:
        raw_input = inputs
        logging.info(f'[raw_input] {raw_input}')
        chatbot.append((inputs, ""))
        yield chatbot, history, "等待响应"

    # Generate API request
    headers, payload = generate_payload(inputs, top_p, temperature, history, system_prompt, stream)
    history.append(inputs)
    history.append(" ")  # Placeholder for response

    # Make API request with retry logic
    retry = 0
    while True:
        try:
            response = requests.post(
                API_CONFIG['api_url'],
                headers=headers,
                proxies=API_CONFIG['proxies'],
                json=payload,
                stream=True,
                timeout=API_CONFIG['timeout']
            )
            break
        except Exception:
            retry += 1
            chatbot[-1] = ((chatbot[-1][0], TIMEOUT_BOT_MSG))
            retry_msg = f"，正在重试 ({retry}/{API_CONFIG['max_retry']}) ……" if API_CONFIG['max_retry'] > 0 else ""
            yield chatbot, history, "请求超时" + retry_msg
            if retry > API_CONFIG['max_retry']:
                raise TimeoutError("Maximum retry attempts exceeded")

    # Process streaming response
    if stream:
        gpt_replying_buffer = ""
        is_head_of_the_stream = True
        stream_response = response.iter_lines()
        
        while True:
            try:
                chunk = next(stream_response)
                
                # Skip the first frame which doesn't contain content
                if is_head_of_the_stream:
                    is_head_of_the_stream = False
                    continue
                
                if not chunk:
                    continue
                    
                try:
                    # Parse the chunk
                    chunk_data = json.loads(chunk.decode()[6:])
                    
                    # Check if this is the end of the stream
                    if len(chunk_data['choices'][0]["delta"]) == 0:
                        logging.info(f'[response] {gpt_replying_buffer}')
                        break
                    
                    # Process the main body of the data stream
                    status_text = f"finish_reason: {chunk_data['choices'][0]['finish_reason']}"
                    
                    # Update the reply buffer with new content
                    gpt_replying_buffer += chunk_data['choices'][0]["delta"]["content"]
                    history[-1] = gpt_replying_buffer
                    chatbot[-1] = (history[-2], history[-1])
                    
                    yield chatbot, history, status_text
                    
                except Exception as e:
                    # Handle parsing errors
                    traceback.print_exc()
                    yield chatbot, history, "Json解析不合常规，很可能是文本过长"
                    
                    # Get the full error message
                    chunk = get_full_error(chunk, stream_response)
                    error_msg = chunk.decode()
                    
                    # Handle specific error cases
                    if "reduce the length" in error_msg:
                        chatbot[-1] = (history[-1], "[Local Message] Input (or history) is too long, please reduce input or clear history by refleshing this page.")
                        history = []
                        
                    yield chatbot, history, "Json解析不合常规，很可能是文本过长" + error_msg
                    return
                    
            except StopIteration:
                # End of stream
                break


