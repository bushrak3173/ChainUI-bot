#access env variables
import os
from dotenv import load_dotenv
#AWS integration for Claude models
from langchain_aws import ChatBedrock
#LC util for doc loading and splitting
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
#message schema for structured prompts
from langchain.schema.messages import SystemMessage, HumanMessage
#Postgre and uuid support
import psycopg2
import uuid
#API key available
load_dotenv()
#memory module for convo history
from langchain.memory import ConversationBufferMemory

from dataclasses import dataclass
from datetime import datetime

#data structure for storing chat messages
@dataclass
class ChatMessageDTO:
    user_input: str
    bot_response: str
    timestamp: datetime = datetime.utcnow()
    username: str = "anonymous"


#initialize ChatOpenAI object
class LangChainService:
    def __init__(self):
        try:
            #Connect to Postgre
            self.db_conn = self.connect_to_postgres()
            print("Tables in Portal schema:", self.list_tables_in_portal_schema())
            #Initialize Claude model w Bedrock
            self.model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
            self.llm = ChatBedrock(
            model_id=self.model_id,
            region_name="us-east-1",
            model_kwargs={
                "temperature": 0.5,
                "top_p": 0.9,
                "max_tokens": 500
                    }
                )

            #loading onboarding instruct
            loader = TextLoader(os.path.join(os.path.dirname(__file__), "onboarding.txt"))
            docs = loader.load()

            #Splitting into chunks for better prompt handling
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            chunks = splitter.split_documents(docs)

            #Joining chunks into single system prompt
            system_prompt = "\n\n".join([chunk.page_content for chunk in chunks])

            #Storing as a SystemMessage
            self.cached_context = [SystemMessage(content=system_prompt)]

            #Initializing Memory
            self.memory = ConversationBufferMemory(return_messages=True)

        #    print(self.fetch_from_table("chatmessages", limit=1))


        except Exception as e:
            print(f"Error initializing Bedrock client: {e}")
            self.cached_context = []
            self.memory = ConversationBufferMemory(return_messages=True)

    def connect_to_postgres(self):
        try:
            conn = psycopg2.connect(
                host="devqa-tigerglobal.cluster-cglo4fl4jwye.us-east-1.rds.amazonaws.com",
                port=5432,
                user="dev_tigerglobal_portal_rw",
                password="ghidrC=^EX*?1OAq",
                dbname="dev_tigerglobal"
            )
            print("✅ Connected to PostgreSQL")
            return conn
        except Exception as e:
            print(f"❌ Failed to connect to PostgreSQL: {e}")
            return None

        #LISTS ALL TABLES
    def list_tables_in_portal_schema(self):
        #List all table names in the 'Portal' schema.
        if not self.db_conn:
            print("No DB connection.")
            return []

        try:
            with self.db_conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'portal'
                    ORDER BY table_name;
                """)
                tables = cur.fetchall()
                return [table[0] for table in tables]
        except Exception as e:
            print(f"Error listing tables: {e}")
            return []

    def fetch_from_table(self, table_name, limit=10):
        if not self.db_conn:
            print("No DB connection.")
            return []
        try:
            with self.db_conn.cursor() as cur:
                query = f'''
                SELECT * FROM "{table_name}"
                ORDER BY 1 DESC
                LIMIT %s;
                '''
                cur.execute(query, (limit,))
                return cur.fetchall()
        except Exception as e:
            print(f"Error fetching data from {table_name}: {e}")
            return []

    def save_chat_message(self, dto: ChatMessageDTO):
        if not self.db_conn:
            print("No DB connection.")
            return

        try:
            with self.db_conn.cursor() as cur:


                timestamp = int(dto.timestamp.timestamp())

                # Insert user message
                user_rowkey = str(uuid.uuid4())
                user_query = '''
                INSERT INTO "portal".chatmessage (rowkey, messagebody, username, createdattime)
                VALUES (%s, %s, %s, %s);
                '''

                cur.execute(user_query, (user_rowkey, dto.user_input, dto.username, timestamp))

                # Insert AI response
                ai_rowkey = str(uuid.uuid4())
                ai_query = '''
                INSERT INTO "portal".chatmessage (rowkey, messagebody, username, createdattime)
                VALUES (%s, %s, %s, %s);
                '''

                cur.execute(ai_query, (ai_rowkey, dto.bot_response, f"{dto.username}_system", timestamp))

            self.db_conn.commit()
            print("✅ Chat message saved.")
        except Exception as e:
            print(f"❌ Error saving chat message: {e}")

    def fetch_recent_conversations(self, username, limit=5):
        if not self.db_conn:
            print("No DB connection.")
            return []

        try:
            with self.db_conn.cursor() as cur:
                query = '''
                    SELECT username, messagebody, createdattime
                    FROM portal.chatmessage
                    WHERE username IN (%s, %s)
                    ORDER BY createdattime DESC
                    LIMIT %s;
                '''
                cur.execute(query, (username, f"{username}_system", limit * 2)) # 2 messages per exchange
                rows = cur.fetchall()
                return rows
        except Exception as e:
            print(f"Error fetching recent conversations: {e}")
            return []

    def print_recent_messages(self, limit=10):
        messages = self.fetch_recent_conversations(limit)
        print("\n📥 Recent Messages from DB:")
        for username, message, ts in messages:
            print(f"[{username}] {message} @ {ts}")


    def get_response(self, prompt):
        print("get_response started")
        #load prev conversation hist
        history = self.memory.load_memory_variables({}).get("history", [])
        #construct full message list
        messages = self.cached_context + [HumanMessage(content=prompt)] + history
        #get model's response 
        response = self.llm.invoke(messages)
        #saving interaction to memory (temp RAM)
        self.memory.save_context({"input": prompt}, {"output": response.content})
        print("get_response completed")
        return response.content


    def stream_response(self, prompt):
        try:
            print("stream_response started")
            # Load memory history if available
            history = [] # empty list to store memory history
            if hasattr(self, "memory"): #if there is memory to retrieve
                try:
                    history = self.memory.load_memory_variables({}).get("history", [])
                    print("Loaded memory history:", history)
                except Exception as e:
                    print("Error loading memory:", e)

            # Construct full message list
            messages = self.cached_context + history + [HumanMessage(content=prompt)]
            print("Sending messages to LLM:", messages)

            # Stream the response
            stream = self.llm.stream(messages)
            full_response = ""

            for chunk in stream:
                if chunk.content:
                    full_response += chunk.content
                    yield chunk #send chunk to frontend

            # Save to memory
            if hasattr(self, "memory"):
                try:
                    self.memory.save_context({"input": prompt}, {"output": full_response})
                    print("Saved to memory:", {"input": prompt, "output": full_response})
                except Exception as e:
                    print("Error saving to memory:", e)

            print("stream_response completed")
        except Exception as e:
            print("Error in stream_response:", e)
            raise e



