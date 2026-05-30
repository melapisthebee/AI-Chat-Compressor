========INFO========





Hello! 



This is the lm-compressor! 



The overall goal of this project was to take a large conversation saved as either a .txt, .pdf, .json, or .md file, and compress it into a significantly smaller snippet of pure data.



This form of compression will not preserve any code snippets or conversational data. 



Just the pure file paths and basic architecture of the project you are presumably working on.



This project uses SLQLite to store "Data Sets" of the past conversational data. 



You can update these "Data Sets" (We will call them projects) by clicking on it and dropping in the new project data.





=======WARNING=======





This project is in it's Alpha stage. 



Expect bugs and unpredictable behavior. 



It is not recommended to use this for enterprise. 



It's not recommended to use AI for enterprise in general. 



I'm talking about you MicroSlop.





=======QUICK START=======





It's quick because it's easy. Just follow along and I'm sure you will be fine.



1: Ensure python is installed.

&#x09;I'm sure it is, just want to make sure you can run the program. 

Use Google to assist with this if you haven't installed python yet. 

If you can't install python, sucks to be you.



2: Create the python virtual environment.

&#x09;This is a straight-forward process. 

Just do as I say and everything will be sunshine and rainbows.

&#x20;

&#x09;"python -m venv .venv"



Congrats! You made a Python Virtual Environment!



3: Activate the venv and install the necessary dependencies.

&#x09;

&#x09;a: "./.venv/Scripts/activate"

&#x09;b: "pip install -r requirements.txt"



Depending on your internet and compute, the time to install everything varies from less than 30 seconds to never.



4: Fill the .env (Environment file) with your URL endpoint, API Token, and model of choice.

If you are missing the file, you should create it ".env" in the project root. 

This is the same directory as the README.md.

The .env should look something like this:



LM\_STUDIO\_BASE\_URL="http://192.0.0.0:1234/v1"

LM\_STUDIO\_API\_KEY="{depends on provider}"

DEFAULT\_COMPRESSION\_MODEL="qwopus3.5-9b-coder-mtp"



5: Run the project and hope it boots.

&#x09;In the project root, run "python app.py"





=======HOW TO RUN=======





Operating the project is very straight forward. 

Making sure to run the project inside the venv(see above), you are to type the name of the project(or click a previously made project), drag and drop a ".md", a ".txt", a ".json", or a ".pdf" file inside of the top window. 

The program will automatically start the compression. 

You can then click the "Copy Context State" button once the program finished compression. You can choose to not copy it and close the program due to the existence of the database at "/storage". 

Deleting this .db file will wipe all projects, so be cautious. 





=======CONTRIBUTING=======



Artificial Intelligence is a powerful tool, but it is not a replacement for human intellect and our ability to create and innovate. 



At the end of the day, AI is a complex autocomplete, regardless of it's architecture. 



Because of this inherit limitation, autocompleted code has to be viewed as flawed and defective until proven not though extensive tests and review. 



AI was used to aid in the creation of this program, so AI is allowed to aid in the assistance of adding features and fixing potential/ current issues. 



If AI is used, you MUST disclose that it has been used so the proper testing can be run on the pull request in question. 



AI is NOT allowed to create issue or pull requests. 



If AI is used to add feature and/or fix issues, then you must AT LEAST be able to write in your own words what the added/modified code does and how it aligns with the projects core function. 



=======INFO=======





This program is delivered AS-IS. 

If something goes catastrophic with your computational device, the developer(s), contributor(s), and maintainer(s) of this program are not responsible.



See LISCENSE.md for the ToS of this program.





Edited: 05/30/2026

