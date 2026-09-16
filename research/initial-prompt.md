# Initial Prompt

## Context

Act as a senior full-stack software engineer and an expert on the Elite Dangerous third-party developer ecosystem (including APIs like Spansh, EDDN, and Canonn)

## Aim

Produce a Python CLI application that can query the Spansh API for bodies that hold Codex entries that the current user has not yet found.

Codex entries broadly fall into these categories:
  - Biology
  - Cloud
  - Anomalies

The application will take one of these categories as a command line argument, and then output a list of the bodies that have codex entries for that category along with the distance from the current system.
It should output the top ten nearest systems, the distance and the new codex entries that can be found there.

The application will need to read the users journal directory to determine the current system and codex entries that the user has not yet found.  It will need to construct a query to the spansh bodies API to find the closest bodies to the current system that have codex entries for the category.


## Planning

Need to be able to read the users's journal file to determine:
- Current system
- Codex entries that they have not yet found for this category

I suggest building up as follows:

### First POC

A python script that reads the journal and outputs the current system

### Second POC

A python script that reads the journal and outputs the codex entries for the Cloud category that the user has not yet found

### Third POC

This is where we start querying the Spansh API.
Read `spansh_api.md` which will point you in the right direction.  Ensure you don't query the API more than once per second else we may get throttled or banned.


## Journal directory

Use a const or config variable to determine the path to your Elite Dangerous journal directory.

In my case you'll find the journal directory at `/mnt/c/Users/vladi/Saved Games/Frontier Developments/Elite Dangerous`
as I'm running from WSL , but if this software was distributed then it would be a different path and likely a Windows shaped path.

