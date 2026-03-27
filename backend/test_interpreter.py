import asyncio
from agents.interpreter_agent import get_interpreter_agent, generate_plan

async def test():
    agent = await get_interpreter_agent()
    user_req = "Scheduled weekly work updates meeting for Arun and Sarveswara get their mail id from employee table"
    try:
        plan = generate_plan(agent, user_req)
        print("SUCCESS!")
        print(plan)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
