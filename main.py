import os; os.environ['no_proxy'] = '*' 
import gradio as gr 
import threading
import webbrowser
import time
import logging
from predict import predict
from toolbox import format_io, find_free_port

# Configuration module
class Config:
    def __init__(self):
        try: 
            from config_private import proxies, WEB_PORT
        except: 
            from config import proxies, WEB_PORT
        
        self.proxies = proxies
        self.PORT = find_free_port() if WEB_PORT <= 0 else WEB_PORT
        self.initial_prompt = "Serve me as a writing and programming assistant."
        self.title = "ChatGPT 学术优化"
        self.title_html = """<h1 align="center">ChatGPT 学术优化</h1>"""

# Setup logging
def setup_logging():
    os.makedirs('gpt_log', exist_ok=True)
    logging.basicConfig(filename='gpt_log/chat_secrets.log', level=logging.INFO, encoding='utf-8')
    print('所有问询记录将自动保存在本地目录./gpt_log/chat_secrets.log，请注意自我隐私保护哦！')

# Browser auto-open function
def auto_open_browser(port):
    print(f"URL http://localhost:{port}")
    def open(): 
        time.sleep(2)
        webbrowser.open_new_tab(f'http://localhost:{port}')
    t = threading.Thread(target=open)
    t.daemon = True
    t.start()

# Main UI builder
def build_ui(config):
    # Import functionalities
    from functional import get_functionals
    functional = get_functionals()
    
    from functional_crazy import get_crazy_functionals
    crazy_functional = get_crazy_functionals()
    
    from check_proxy import check_proxy
    
    gr.Chatbot.postprocess = format_io
    
    with gr.Blocks() as demo:
        gr.HTML(config.title_html)
        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.Chatbot()
                chatbot.style(height=1000)
                history = gr.State([])
                TRUE = gr.State(True)
                FALSE = gr.State(False)
            with gr.Column(scale=1):
                with gr.Row():
                    with gr.Column(scale=12):
                        txt = gr.Textbox(show_label=False, placeholder="Input question here.").style(container=False)
                    with gr.Column(scale=1):
                        submitBtn = gr.Button("Ask", variant="primary")
                with gr.Row():
                    # Create functional buttons
                    for k in functional:
                        variant = functional[k].get("Color", "secondary")
                        functional[k]["Button"] = gr.Button(k, variant=variant)
                    for k in crazy_functional:
                        variant = crazy_functional[k].get("Color", "secondary")
                        crazy_functional[k]["Button"] = gr.Button(k, variant=variant)
                
                statusDisplay = gr.Markdown(f"{check_proxy(config.proxies)}")
                systemPromptTxt = gr.Textbox(
                    show_label=True, 
                    placeholder="System Prompt", 
                    label="System prompt", 
                    value=config.initial_prompt
                ).style(container=True)
                
                with gr.Accordion("arguments", open=False):
                    top_p = gr.Slider(
                        minimum=0, 
                        maximum=1.0, 
                        value=1.0, 
                        step=0.01,
                        interactive=True, 
                        label="Top-p (nucleus sampling)"
                    )
                    temperature = gr.Slider(
                        minimum=0, 
                        maximum=5.0, 
                        value=1.0, 
                        step=0.01, 
                        interactive=True, 
                        label="Temperature"
                    )

        # Event handlers
        txt.submit(predict, [txt, top_p, temperature, chatbot, history, systemPromptTxt], 
                  [chatbot, history, statusDisplay])
        submitBtn.click(predict, [txt, top_p, temperature, chatbot, history, systemPromptTxt], 
                       [chatbot, history, statusDisplay], show_progress=True)
        
        # Functional buttons
        for k in functional:
            functional[k]["Button"].click(
                predict, 
                [txt, top_p, temperature, chatbot, history, systemPromptTxt, TRUE, gr.State(k)], 
                [chatbot, history, statusDisplay], 
                show_progress=True
            )
        
        # Crazy functional buttons
        for k in crazy_functional:
            crazy_functional[k]["Button"].click(
                crazy_functional[k]["Function"], 
                [txt, top_p, temperature, chatbot, history, systemPromptTxt, gr.State(config.PORT)], 
                [chatbot, history, statusDisplay]
            )

        demo.title = config.title
        return demo

# Main application entry point
def main():
    setup_logging()
    config = Config()
    demo = build_ui(config)
    auto_open_browser(config.PORT)
    demo.queue().launch(server_name="0.0.0.0", share=True, server_port=config.PORT)

if __name__ == "__main__":
    main()
