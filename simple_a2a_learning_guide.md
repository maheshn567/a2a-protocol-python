# A2A Communication — Simple Learning Guide

## What You Will Learn

This guide explains how AI agents communicate with each other.

You will learn:

- How agents find each other
- How agents send requests and responses
- How to stream live updates
- How to use webhooks for background tasks
- How to build a simple project with Python

## Prerequisites

You should know:

- Basic Python
- Basic HTTP and REST APIs
- Basic JSON
- Python 3.7+
- How to use a code editor

---

## 1. Agent Discovery

Before two agents can communicate, they need to find each other.

An agent can publish an **Agent Card**.

An Agent Card is a JSON file that tells other agents:

- Who the agent is
- What it can do
- Where to send requests
- What information it needs

Think of it like a **business card for an agent**.

---

## 2. Communication Methods

There are three main ways agents can communicate.

### Synchronous Communication

One agent sends a request and waits for the answer.

**Example:**

```text
Client → Request → Server
Client ← Response ← Server
```

Use this for quick tasks.

### Asynchronous Communication

The client sends a request and does not wait.

The server gives a **task ID** and works in the background.

Later, the server sends the result.

Use this for long tasks.

### Server-Sent Events (SSE)

SSE lets the server send live updates to the client.

For example:

```text
Starting...
20% complete
50% complete
80% complete
Done!
```

Use SSE when you want to show progress or live data.

### Webhooks

A webhook is a callback from one server to another.

When a task is finished, the server sends a request to a webhook URL.

Use webhooks for:

- Long-running tasks
- Notifications
- Background jobs
- Event-based systems

---

## 3. SSE vs Webhooks

| SSE | Webhooks |
|---|---|
| Live connection | No permanent connection |
| Server sends live updates | Server sends a callback |
| Good for progress updates | Good for task completion |
| Good for streaming | Good for background tasks |

**Simple rule:**

- Use **SSE** for live updates.
- Use **Webhooks** for final notifications.

---

# Project: Weather Agent

You will build a simple weather system with two agents.

## Weather Agent

The weather agent will:

- Provide weather information
- Publish an Agent Card
- Handle normal requests
- Support SSE
- Support background tasks and webhooks

## Client Agent

The client will:

- Find the weather agent
- Send weather requests
- Show the result
- Test SSE
- Test webhooks

---

# 4. Build the Project

## Step 1: Set Up Python

Create a project folder.

Create a virtual environment.

Install the libraries you need for:

- FastAPI
- Uvicorn
- HTTP requests

---

## Step 2: Build the Weather Agent

Create a simple web server.

It should:

- Provide an Agent Card
- Accept weather requests
- Return sample weather data
- Support normal requests
- Support streaming
- Support background tasks

You can use fake weather data at first.

---

## Step 3: Add Agent Discovery

The client should:

1. Request the Agent Card.
2. Read the JSON.
3. Find the agent's endpoints.
4. Understand what the agent can do.
5. Send requests to the correct endpoint.

A common discovery URL is:

```text
/.well-known/agent.json
```

---

## Step 4: Build the Client

The client should:

- Find the weather agent
- Ask for a city
- Send the request
- Show the weather
- Handle errors

Example:

```text
User: Weather in Bangalore

Client → Weather Agent
Client ← 28°C, Sunny
```

---

## Step 5: Add SSE

Add a streaming endpoint.

The server can send:

```text
Starting weather check...
Checking data...
Preparing result...
Weather: 28°C, Sunny
Done!
```

The client should display each update as it arrives.

---

## Step 6: Add Webhooks

Create a webhook receiver.

The flow is:

```text
Client → Server
          ↓
       Task starts
          ↓
       Task finishes
          ↓
Server → Webhook
```

The webhook receives the final result.

---

# 5. Why Use FastAPI?

You can use Flask, but **FastAPI is a good choice** for this project.

### Benefits of FastAPI

- Fast
- Easy to build APIs
- Supports async code
- Supports streaming
- Automatic API documentation
- Uses Python type hints

FastAPI also provides:

```text
/docs
```

This page lets you test your API in a browser.

---

# 6. Simple Project Structure

Your project can look like this:

```text
a2a-project/
│
├── server/
│   └── weather_agent.py
│
├── client/
│   └── client.py
│
├── webhook/
│   └── receiver.py
│
└── tests/
    └── test_agent.py
```

---

# 7. Questions to Understand

After building the project, make sure you can answer:

1. How does one agent find another agent?
2. What is an Agent Card?
3. When should you use synchronous communication?
4. When should you use asynchronous communication?
5. What is SSE?
6. What is a webhook?
7. When should you use SSE instead of a webhook?
8. What happens to a task from start to finish?

---

# 8. Things to Try

Once the basic project works, try:

- Connect multiple clients
- Test an invalid city
- Create a long-running task
- Add another agent, such as a news agent
- Create an agent registry

---

# 9. Common Mistakes

### Hardcoding Everything

Do not hardcode agent URLs everywhere.

Use discovery instead.

### Doing Too Much at Once

Start with simple request-response communication.

Then add:

1. Discovery
2. SSE
3. Webhooks
4. More agents

### Ignoring Errors

Handle:

- Network errors
- Timeouts
- Invalid requests
- Invalid responses

### Not Testing

Test each part separately and then test the whole system.

---

# 10. Next Steps

After the basic project works, you can:

1. Add more agents
2. Add authentication
3. Use a real weather API
4. Build an agent registry
5. Use Docker
6. Deploy the project
7. Learn the A2A protocol
8. Add monitoring and logging

---

# Key Takeaways

The main ideas are:

- **Discovery** → Find other agents
- **Agent Cards** → Describe an agent
- **Synchronous requests** → Good for quick tasks
- **Asynchronous tasks** → Good for long tasks
- **SSE** → Good for live updates
- **Webhooks** → Good for task completion
- **FastAPI** → A good framework for building the project

## Simple Learning Order

Learn in this order:

```text
1. Basic request/response
        ↓
2. Agent discovery
        ↓
3. Agent Cards
        ↓
4. SSE streaming
        ↓
5. Async tasks
        ↓
6. Webhooks
        ↓
7. Multiple agents
```

## Final Goal

The goal is not to memorize everything.

Understand:

- How agents find each other
- How agents communicate
- When to use each communication method
- How to build a simple A2A system

**Start simple, test each step, and add features one at a time.**
