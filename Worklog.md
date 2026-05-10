## Worklog 10-May-2026
<img width="1583" height="1268" alt="Screenshot 2026-05-11 at 12 53 55 AM" src="https://github.com/user-attachments/assets/dc31385a-3cd3-4b6a-886b-7efa63d7fab4" />
Citations visible for a text based questions 

### Next steps 
- Add a validator agent to validate citation 
- Add a parallel analyzer to store logs of tool calling per query to future analyze the gaps 
- generate permutation of tools needs and add a fallback default tool
- explore chain looping multiple tool getting called in a single llm call when all sent together vs having specified tool for every action
- [Deep Dive] Performance issues with sending lot of tool with little difference that might 
- [Debug] If any chat query hits default tool log their chain of thought differently
- [Good to Have] Show other related queries which user can ask if the default case hits and log this chain of tool calling in 
