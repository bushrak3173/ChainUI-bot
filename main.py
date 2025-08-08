#cl interface
import chainlit as cl



from langchain_service import LangChainService

user_profiles = {}

from datetime import datetime
from langchain_service import LangChainService, ChatMessageDTO

#instance of service
service = LangChainService()
from datetime import datetime
from langchain_service import ChatMessageDTO

#simulating delays
import asyncio

print("Starting main.py")

# CHECKING WHICH SCHEMA TABLE IS IN
import psycopg2

def check_chatmessage_schema():
    try:
        conn = psycopg2.connect(
            host="devqa-tigerglobal.cluster-cglo4fl4jwye.us-east-1.rds.amazonaws.com",
            port=5432,
            dbname="dev_tigerglobal",
            user="dev_tigerglobal_portal_rw",
            password="ghidrC=^EX*?1OAq"
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT table_schema
            FROM information_schema.tables
            WHERE table_name = 'chatmessage';
        """)
        result = cur.fetchone()
        print("Schema for 'chatmessage':", result[0] if result else "Table not found")
        cur.close()
        conn.close()
    except Exception as e:
        print("Error checking schema:", e)

# Run the check once when the script starts
check_chatmessage_schema()

@cl.action_callback(name = "show_recent_convo")
async def show_recent_convo():
    user_id = cl.user_session.get("user_id")
    if user_id:
        await show_recent_conversations(user_id)


async def show_recent_conversations(user_id: str):
    history = service.fetch_recent_conversations(user_id, limit=5) # retrieves last 5 messages

    if not history:
        disclaimer_text = "**Recent_Conversations**\n\n_No chat history found for this user. Start chatting to see messages here later._"
        elements = [
            cl.Text(
                name="Recent Conversations",
                content=disclaimer_text,
                display="side",
                on_click="show_recent_convo"
            )
        ]
        await cl.Message(
            content="Click → Recent_Conversations to view recent chat history. Type a message to start chatting!",
            elements=elements
        ).send()
        return

    history = list(reversed(history))
    summaries = []
    for i in range(0, len(history), 2):
        try:
            user_row = history[i]
            bot_row = history[i + 1]

            if bot_row[0].endswith("_system"):
                user_msg = user_row[1]
                ai_msg = bot_row[1]
            else:
                user_msg = bot_row[1]
                ai_msg = user_row[1]

            summaries.append(f"- **You**: {user_msg[:40]}...\n **Bot**: {ai_msg[:40]}...")
        except IndexError:
            continue


    summary_text = "**Chat History**\n" + "\n\n".join(summaries)
    elements = [
        cl.Text(
            name="Recent_Conversations",
            content=summary_text,
            display="side",
            on_click="show_recent_convo"
        )
    ]
    await cl.Message(
        content="Click → Recent_Conversations to view recent chat history. Type a message to start chatting!",
        elements=elements
    ).send()

#assigns user id and fetches previous convos
@cl.on_chat_start
async def start():
    if cl.user_session.get("authenticated"):
        username = cl.user_session.get("username", "Anonymous")
        avatar = cl.user_session.get("avatar", None)
        user_id = cl.user_session.get("user_id", f"user_{datetime.utcnow().timestamp()}")

        cl.user_session.set("user_id", user_id)

        await cl.Message(content=f"Welcome back, **{username}**!").send()

        # Fetch and display recent conversations
        history = service.fetch_recent_conversations(user_id, limit=5)
        summaries = []

        for i in range(0, len(history), 2):
            try:
                user_msg = history[i][1] if history[i][0] != "SYSTEM" else history[i+1][1]
                ai_msg = history[i+1][1] if history[i][0] != "SYSTEM" else history[i][1]
                summaries.append(f"- **You**: {user_msg[:40]}...\n  **Bot**: {ai_msg[:40]}...")
            except IndexError:
                continue

        summary_text = "**Recent Conversations**\n" + "\n\n".join(summaries)

        elements = [
            cl.Text(
                name="Recent_Conversations",
                content=summary_text,
                display="side",
                on_click="show_recent_convo"
            )
        ]

        await cl.Message(
            content="Click → Recent_Conversations to view recent chat history.",
            elements=elements
        ).send()

        return

    #Assign a unique user ID if not already set
    global user_profiles
    if "user_profiles" not in globals():
        user_profiles = {}

    await cl.Message(content="Welcome to the BMO AI Chatbot!").send()

    # Ask user to choose between login or create profile
    action_msg = cl.AskActionMessage(
        content="Would you like to log in or create a profile?",
        actions=[
            cl.Action(name="login", value="login", label="Log In", payload={}),
            cl.Action(name="create", value="create", label="Create Profile", payload={})
        ]
    )

    action = await action_msg.send()
    print("Action selected:", action)

    username = None

    # Handle profile creation
    if action["name"] == "create":
        username_msg = await cl.AskUserMessage("Enter a new username:").send()
        username = username_msg["output"].strip()

        if username in user_profiles:
            await cl.Message(content="That username is already taken. Please restart and choose a different one.").send()
            return

        avatar_msg = await cl.AskUserMessage("Paste a link to your profile picture (or leave blank):").send()
        avatar = avatar_msg["output"].strip() or None

        user_profiles[username] = avatar

        await cl.Message(content="Profile created successfully! Starting a new session... Re-enter UserName").send()

        cl.user_session.set("authenticated", True)


# Handle login
    elif action["name"] == "login":
        if not user_profiles:
            await cl.Message(content="No profiles exist yet. Please restart and create one.").send()
            return

        username_msg = await cl.AskUserMessage(f"Enter your username:").send()
        username = username_msg["output"].strip()

        if username not in user_profiles:
            await cl.Message(content="Username not found. Please restart or create a new profile.").send()
            return

        await cl.Message(content=f"Welcome back, **{username}**!").send()

        cl.user_session.set("authenticated", True)



    else:
            await cl.Message(content=f"Unexpected action: {action.value}").send()
            return

    # Set session data
    cl.user_session.set("username", username)
    cl.user_session.set("avatar", user_profiles.get(username))



#run when user msg sent
# sends incoming msgs to backend + displays response
@cl.on_message
async def on_message(message: cl.Message):
    username = cl.user_session.get("username", "Anonymous")
    avatar = cl.user_session.get("avatar", None)
    # Start a message object with empty content
    print("on message triggered")

    user_id = cl.user_session.get("user_id")

    if not user_id:
        user_id = message.content.strip()
        cl.user_session.set("user_id", user_id)
        await cl.Message(f"Thanks, {user_id}! Your chat history will now be saved.").send()
        await show_recent_conversations(user_id)
        return


    response = cl.Message(content="")
    await response.send()

    response_text=""

    #streaming llm tokens
    try:
         for chunk in service.stream_response(message.content):
            if chunk.content:
                response_text += chunk.content
                response.content += chunk.content
                await response.send()
    except Exception as e:
        response.content = f"Error: {e}"
        await response.update()
        # Save to DB WITH DTO
    dto = ChatMessageDTO(
        user_input=message.content, #user msg
        bot_response=response_text, #LLM Response
        timestamp=datetime.utcnow(), # time of interaction
        username=cl.user_session.get("user_id") # UserID of session
    )

    service.save_chat_message(dto)

    service.print_recent_messages()

    cl.user_session.set("history", cl.user_session.get("history", []) + [(message.content, response_text)])

    print("on_message ended")
    print("Assigned user ID:", user_id)


