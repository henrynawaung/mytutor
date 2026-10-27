@echo off
rem Starts n8n with the two nodes myTutor needs (Execute Command, Local File Trigger) enabled.
rem n8n 2.0 disables them by default for security.
set NODES_EXCLUDE=[]
n8n start
