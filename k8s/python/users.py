# This script clones a GitHub repository, automates the setup of a Python virtual environment and installs application dependencies.

# Define paths using environment variables
$documentsPath = "$env:USERPROFILE\Documents"
$envPath = "$documentsPath\python-v-env"
$appPath = "$documentsPath\load_platform"

# Clone the GitHub repository into the Documents folder
git clone https://github.com/your-username/your-repository.git $appPath

# Create a virtual environment to isolate project dependencies and avoid conflicts with other Python projects.
python -m venv $envPath

# Navigate to the application directory
Set-Location $appPath

# Use the virtual environment's Python to upgrade pip
& "$envPath\Scripts\python.exe" -m pip install --upgrade pip

# Install dependencies using the virtual environment's pip
& "$envPath\Scripts\pip.exe" install -r requirements.txt

# Instalar Uvicorn si no está incluido en requirements.txt
pip install uvicorn

# Ejecutar la aplicación FastAPI utilizando Uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000

# Why does this script is proposing to use uvicorn for launching the App?
#
# Understanding ASGI and WSGI in Python Web Applications
#
# Key Differences Between WSGI and ASGI
# WSGI (Web Server Gateway Interface) is a standard interface between web servers and synchronous Python web applications.
# It was designed for a time when web applications were predominantly synchronous, handling one request at a time.
# ASGI (Asynchronous Server Gateway Interface), on the other hand, is a successor to WSGI, created to support asynchronous applications.
# ASGI allows for handling multiple connections concurrently and is well-suited for modern web applications that require real-time communication,
# such as WebSockets.
# 
# Advantages and Disadvantages
# WSGI Advantages:
# 
# Simplicity: Easy to implement and sufficient for traditional web applications.
# Wide Support: Well-established with extensive tooling and community support.
# WSGI Disadvantages:
# 
# Limited Concurrency: Cannot handle asynchronous calls efficiently.
# Not Suitable for Real-Time Applications: Lacks support for protocols like WebSockets.
# ASGI Advantages:
# 
# Asynchronous Support: Handles asynchronous tasks efficiently, improving performance.
# Versatility: Supports long-lived connections and protocols beyond HTTP, such as WebSockets.
# ASGI Disadvantages:
# 
# Complexity: Slightly more complex to implement than WSGI.
# Less Mature: Newer standard with a smaller ecosystem compared to WSGI.
# Why Use Uvicorn in a Production Environment
# Uvicorn is a fast, lightweight ASGI server ideal for running asynchronous Python web applications like those built with FastAPI.
# It leverages modern programming patterns, providing high performance by handling multiple requests concurrently without blocking.
# Using Uvicorn in production allows applications to fully utilize the asynchronous capabilities of FastAPI, resulting in improved scalability and responsiveness,
# especially under high load or when dealing with I/O-bound operations.
