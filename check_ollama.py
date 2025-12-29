from services.ollama_llm import check_ollama_status

if check_ollama_status():
    print("Ollama is running")
else:
    print("Ollama is NOT running")
