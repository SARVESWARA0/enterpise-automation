import psycopg2
conn = psycopg2.connect('postgresql://postgres:1234@localhost:5432/enterprise_autopilot')
cur = conn.cursor()
cur.execute("SELECT workflow_run_id, workflow_type, input_payload FROM workflow_runs ORDER BY created_at DESC LIMIT 5")
print('all runs:', cur.fetchall())
