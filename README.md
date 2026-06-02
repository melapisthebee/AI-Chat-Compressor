\## START





Welcome!



This is the AI Chat Compressor, shortened to "lm-compressor" in the root directory. This project was

&#x09;built specifically for LM Studio.



The purpose of this program, in a nutshell, is to compress a large conversation

&#x09;in the format of ".txt", ".pdf", ".md", and/or ".json", into a significantly smaller,

&#x09;high quality, structurally based json stored inside of a manipulatable SQLite based DataBase file.



These json files, which we will refer to as "projects" from this moment forward, can be retrieved at any time. All that

&#x09;is required is for the database file(.db) inside of "./storage/" to remain intact and secured.





\#### WARNING





This program is in an ALPHA state, and is delivered AS-IS.



The developer(s), contributor(s), maintainer(s), owner(s), and hosting service(s)

&#x09;are not responsible for any lost, damaged, and/or destroyed software and/or

&#x09;hardware that this program may or may not cause.





\## QUICK START

\#### It's quick because it's easy.



1: `Ensure python is installed.`



&#x09;Verify with `python -m pip --version` :
Should output something like `pip 26.1.1 from C:\\\\Python314\\\\Lib\\\\site-packages\\\\pip (python 3.14)`

If python is not installed, you can download it at `https://www.python.org/downloads/`, then verify the installation using the `pip` command above.





2: `Create the python virtual environment.`

&#x20;

&#x09;Run `python -m venv .venv` in `lm-compressor/` :

&#x09;Should see a `.venv` appear in the directory





3: Activate the venv and install the necessary dependencies.

&#x09;

&#x09;Run `./.venv/Scripts/activate` :

&#x09;then `pip install -r requirements.txt`





4: Fill the `.env` file in the program's root directory with your LM Studio URL, API Token, and Model of choice.





5: Launch





============HOW TO RUN============





Operating the project is very straight forward.

Making sure to run the project inside the venv(see above),

&#x09;you are to type the name of the project(or click a previously made project),

&#x09;drag and drop a ".md", a ".txt", a ".json", or a ".pdf" file inside of the top window.

The program will automatically start the compression.

You can then click the "Copy Context State" button once the program finished compression.

You can choose to not copy it and close the program due to the existence of the database at "/storage".

Deleting this .db file will wipe all projects, so be cautious.





============CONTRIBUTING============



Artificial Intelligence is a powerful tool, but it is not a replacement for human intellect and our ability to create and innovate.

At the end of the day, AI is a complex autocomplete, regardless of it's architecture.

Because of this inherit limitation, autocompleted code has to be viewed as flawed and defective until proven not though extensive tests and review.

AI was used to aid in the creation of this program, so AI is allowed to aid in the assistance of adding features and fixing potential/ current issues.

If AI is used, you MUST disclose that it has been used so the proper testing can be run on the pull request in question.

AI is NOT allowed to create issue or pull requests.

If AI is used to add feature and/or fix issues,

&#x09;then you must AT LEAST be able to write in your own words what the added/modified code does and how it aligns with the projects core function.

&#x09;This is for everyone's benefit. You get to Vibe-Code, so we get to verify.



=============\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_=============

&#x09;      Edited: 05/31/2026

