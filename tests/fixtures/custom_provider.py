from litellm import CompletionResponse

class CustomProvider:
    def __init__(self, config):
        self.config = config

    def completion(self, messages, **kwargs):
        return CompletionResponse(
            choices=[{
                "message": {
                    "content": "Custom provider response",
                    "role": "assistant"
                }
            }]
        )