#!/usr/bin/env python
# coding: utf-8


import os
import requests 
import urllib
import datetime
import sys
import json
import os
import pdb
import urllib.parse
from tabulate import tabulate

# Read configuration.json from environment variable GITLAB_CONFIG
ENV_VARIABLE_NAME = "GITLAB_CONFIG"

def main(args):
    d = createDeligator()
    d.translate(args)
    
def createDeligator():
    configuration = Configuration()
    requestFactory = RequestFactory(configuration)
    resources = GitlabResources(configuration)
    executor = GitLab(requestFactory, resources)

    # init apis
    apis = [BranchApi(), PipelineApi(), BoardApi(), IssueMoveApi(), IssueApi(), MergeRequestApi(), LabelsApi()]
    address = "{}/api/{}/projects/{}".format(configuration.getHostAddress(),\
            configuration.getApiVersion(),\
            configuration.getProjectId())
    for api in apis:
        api.setup(address, requestFactory)
    
    return Command(executor, apis)


class Configuration(object):
    
    def __init__(self):
        configFile = "./configuration.json"
        if ENV_VARIABLE_NAME in os.environ:
            configFile = os.environ[ENV_VARIABLE_NAME]
        with open(configFile, "r") as file:
            jFile = json.load(file)
            self._accessToken = jFile["access-token"]
            self._gitlabHost = jFile["host"]
            self._apiVersion = jFile["api-version"]
            self._projectId = jFile["project-id"]
            
    def getToken(self):
        return self._accessToken
    
    def getHostAddress(self):
        return self._gitlabHost
    
    def getApiVersion(self):
        return self._apiVersion
    
    def getProjectId(self):
        return self._projectId

class Util(object):

    def lineBreak(text, chars):
        if type(text) is not str:
            return text
        for i in range(len(text)):
            if i > 0 and i % chars == 0:
                text = text[0:i] + "\n" + text[i:len(text)]
                
        return text

class GitlabResources(object):
    
    def __init__(self, configuration):
        self.address = "{}/api/{}/projects/{}".format(configuration.getHostAddress(),\
            configuration.getApiVersion(),\
            configuration.getProjectId())

    def getIssueWithLabels(self, labels):
        labels = ",".join(labels)
        return self.address + "/issues?labels={}&state=opened".format(labels)
    
    def getIssueById(self, issueId, opened):
        op = ""
        if opened:
            op = "?state=opened"
        return self.address + "/issues/{}{}".format(issueId, op)

    def putLabelsToIssue(self, issueIid, labelsArray):
        return self.address + "/issues/{}?labels={}".format(issueIid, ",".join(labelsArray))

    def putAssignIssue(self, issueId, userId):
        return self.address + "/issues/{}?assignee_ids={}".format(issueId, userId)
    
    def getPipelines(self, username = None, sort = "desc"):
        args = "sort={}".format(sort)
        if username is not None:
            args += "&username={}".format(username)
        return self.address + "/pipelines?{}".format(args)
    
    def getProjectBoards(self):
        return self.address + "/boards"
    
    def getIssueNotes(self, issueId):
        return self.address + "/issues/{}/notes?sort=asc".format(issueId)


class Utils(object):

    def encode(text):
        return urllib.parse.quote(text)

    def jsonDump(jsonDict):
        result = {}
        for key in jsonDict:
            result[key] = Utils.encode(jsonDict[key])
        return result

    def lineBreak(text, chars):
        if type(text) is not str:
            return text
        for i in range(len(text)):
            if i > 0 and i % chars == 0:
                text = text[0:i] + "\n" + text[i:len(text)]
                
        return text

class RequestFactory(object):

    def __init__(self, configuration):
        self.config = configuration

    def get(self, endpoint):
        print(endpoint)
        r = requests.get(url = endpoint, headers = {'private-token': '{}'.format(self.config.getToken())})
        return r

    def post(self, endpoint, requestDataDict):
        r = requests.post(url = endpoint, data = requestDataDict, headers = {'private-token': '{}'.format(self.config.getToken())})
        return r
    
    def put(self, endpoint):
        r = requests.put(url = endpoint,         headers = {'private-token': '{}'.format(self.config.getToken())})
        return r

class GitLab(object):

    def __init__(self, requestFactory, resources):
        self.requestFactory = requestFactory
        self.res = resources

    def removeReadyLabel(self, panelName):
        endpoint = self.res.getIssueWithLabels([panelName, "Ready"]) 
        answer = self.requestFactory.get(endpoint)
        answerJson = answer.json()
       
        issuesWithLabels = {}   
        for issue in answerJson:
            labels = issue["labels"]
            print("Name: {}, iid={}, Labels: {}".format(issue["title"], issue["iid"], labels))
            if "Ready" in labels:
                issueId = issue["iid"]
                labels.remove("Ready")
                issuesWithLabels[issueId] = labels
                
        for issue, labels in issuesWithLabels.items():
            endpoint = self.res.putLabelsToIssue(issue, labels) 
            print("remove label {}".format(endpoint))
            answer = self.requestFactory.put(endpoint)
            
    def moveToPanel(self, issueId, labelName):
        answer = self.requestFactory.get(self.res.getProjectBoards())
        allLabels = []
        boards = answer.json()
        for b in boards:
            lists = b["lists"]
            for list in lists:
                allLabels.append(list["label"]["name"])
            
        if labelName not in allLabels:
            print("List {} not known.\nKnown lists {}", labelName, allLabels)
            return
        
        answer = self.requestFactory.get(self.res.getIssueById(issueId, True)).json()
        labels = answer["labels"]
        for panelLabel in allLabels:
            if panelLabel in labels:
                print("Remove list label {}".format(panelLabel))
                labels.remove(panelLabel)
        
        labels.append(labelName)  
        labels = [Utils.encode(x) for x in labels]
        print("Set labels {}".format(labels))
        answer = self.requestFactory.put(self.res.putLabelsToIssue(issueId, labels))
        print(answer.json())
        
    def assignToUser(self, issueId, userName):
        answer = self.requestFactory.get(self.res.getUsersByName(userName))
        users = answer.json()
        
        foundUser = None
        for user in users:
            if user["username"] == userName:
                foundUser = user
                break

        assert foundUser is not None, "No user found"
            
        answer = self.requestFactory.put(self.res.putAssignIssue(issueId, foundUser["id"]))
        print(answer.json())
    
    def unassignIssue(self, issueId):
        answer = self.requestFactory.put(self.res.putAssignIssue(issueId, "0"))
        print(answer.json())
        
        
    def printOpenMergeRequests(self):
        answer = self.requestFactory.get(self.res.getOpenMergeRequests()).json()
        
        rows = []
        for mr in answer:
            iid = mr["iid"]
            title = mr["title"]
            sourceBranch = mr["source_branch"]
            author = mr["author"]["username"]
            workInProgress = mr["work_in_progress"]
            mergeStatus = mr["merge_status"]
            webUrl = mr["web_url"]
            upVotes = mr["upvotes"]
            userNotesCount = mr["user_notes_count"]
            row = [iid, upVotes, title, author, userNotesCount, workInProgress, mergeStatus, webUrl]
            row = [self.lineBreak(x, 30) for x in row]
            rows.append(row)
        
        print(tabulate(rows, headers=["id", "👍", "title", "author", "notes", "wip" , "status", "url"], tablefmt="simple"))
        
    def printMergeRequest(self, mrId):
        answer = self.requestFactory.get(self.res.getMergeRequest(mrId)).json()
        title = answer["title"]
        description = answer["description"]
        author = answer["author"]["username"]
        upVotes = answer["upvotes"]
        mergeStatus = answer["merge_status"]
        workInProgress = answer["work_in_progress"]
        
        print("Title: {},\nDescription: {},\nAuthor: {},\nUpvotes: {},\nMR-Status: {},\nWIP: {}"                 .format(title, description, author, upVotes, mergeStatus, workInProgress))

        notes = self.requestFactory.get(self.res.getMergeRequestNotes(mrId)).json()
        for note in notes:
            author = note["author"]["username"]
            body = note["body"]
            print("--------\nauthor {}: {}".format(author, body))
        
    def lineBreak(self, text, chars):
        if type(text) is not str:
            return text
        for i in range(len(text)):
            if i > 0 and i % chars == 0:
                text = text[0:i] + "\n" + text[i:len(text)]
                
        return text
    
    def printIssue(self, issueId):
        answer = self.requestFactory.get(self.res.getIssueById(issueId, False)).json()
        notes = Paginator.fetchAll(self.requestFactory, self.res.getIssueNotes(issueId))
        
        description = answer["description"] 
        labels = answer["labels"]
        print("* Description: {}".format(description))
        print("* Lables: {}".format(labels))
        print("* State: {}".format(answer["state"]))
        for note in notes:
            author = note["author"]["username"]
            body = note["body"]
            pdb.set_trace()
            print("--------\nauthor {}: {}".format(author, body))


class Printer(object):

    def out(self, message):
        print(message)


class Paginator(object):

    def fetchAll(requestFactory, apiRequest):
        answer = requestFactory.get(apiRequest)
        totalPages = int(answer.headers["X-Total-Pages"])
        currentPage = int(answer.headers["X-Page"])
        totalElements = int(answer.headers["X-Total"])

        resultElements = [e for e in answer.json()]

        for page in range(currentPage, totalPages):
            page += 1
            pagination = "&page={}".format(page)
            answer = requestFactory.get(apiRequest + pagination)
            [resultElements.append(e) for e in answer.json()]
        return resultElements


class ApiArg(object):

    def getArgToken():
        return "-"

    def isTokenArg(arg):
        return arg.startswith(ApiArg.getArgToken())

    def __init__(self, token, transform = None, required = False, description = "", position = None):
        self._token = "{}{}".format(ApiArg.getArgToken(), token)
        if transform == None:
            self._transform = token
        else:
            self._transform = transform
        self._value = None
        self._required = required
        self._description = description
        self._position = position

    def match(self, arg):
        return arg.startswith(self._token)

    def getToken(self):
        return self._token

    def fetch(self, arg, argPosition):
        if self.match(arg):
            self._value = self._setValue(arg)
            return True
        if self._position is not None and not ApiArg.isTokenArg(arg) and self._position == argPosition:
            self._value = arg
            return True
        return False

    def validate(self):
        return not self._required or self._value is not None

    def isRequired(self):
        return self._required

    def description(self):
        return self._description

    def _setValue(self, arg):
        if arg.startswith(self._token + "="):
            return arg.replace(self._token + "=", "")
        else:
            return arg.replace(self._token, "")

    def getValue(self):
        return self._value

    def transform(self):
        if self._value is not None:
            return "{}={}".format(self._transform, self._value)
        else:
            return ""

class Api(object):

    def setup(self, address, requestFactory):
        self.address = address
        self.requestFactory = requestFactory
        self.helpText = ""
        self._setup()
    

    def _setup(self):
        self._params = []
        self._command = None

    def match(self, command):
        return command == self._command   

    def execute(self, args):
        pass

    def fetchParams(self, args):
        for argPosition, arg in enumerate(args):
            matched = False
            for param in self._params:
                matched = param.fetch(arg, argPosition)
                if matched:
                    break
            if not matched:
                self.help()
                return True
        for param in self._params:
            if not param.validate():
                printer.out("Validation failure")
                self.help()
                return True
        return False

    def apiArgs(self):
        args = "?"
        for param in self._params:
            var = param.transform()
            if var != "":
                args += "&" + var   
        return args    

    def help(self):
        args = []
        for param in self._params:
            addition = ""
            if param.isRequired():
                addition += "[Req]"
            if param._position is not None:
                addition += "[P{}]".format(param._position)
            args.append("{}{}[{}]".format(addition, param.getToken(), param.description()))
        printer.out(" -> {} {} - {}".format(self._command, args, self.helpText))

    def addHelp(self, text):
        self.helpText += text

class PipelineApi(Api):

    def _setup(self):
        self._params = [ApiArg("u", transform = "username", description="username", position = 0), \
                        ApiArg("sort", position = 1),
                        ApiArg("n", description="number of entries", position = 2)]
        self._command = "pipes"

    def testPip(self):
        return {"id": 2, "status": "good", "ref": "pi", "web_url": "test"}

    def execute(self, args):
        if self.fetchParams(args):
            return
        answer = self.requestFactory.get(self.getPipelines())

        numberOfEntries = self._params[2].getValue()

        pipelines = answer.json()
        rows = []
        for index, pip in enumerate(pipelines):
            pipId = pip["id"]
            pipStatus = pip["status"]
            pipRef = pip["ref"]
            pipUrl = pip["web_url"]
            rows.append([pipId, pipStatus, pipRef, pipUrl])
            if numberOfEntries is not None and (index + 1) == int(numberOfEntries):
                break
        printer.out(tabulate(rows, headers=['id', 'status', 'ref', 'url']))

    def getPipelines(self):
        return self.address + "/pipelines{}".format(self.apiArgs())

class IssueApi(Api):

    def _setup(self):
        self._params = [ApiArg("iid", description="id of issue", required = True, position = 0), \
                        ApiArg("a", description="add note", position = 1), \
                        ApiArg("d", description="print discussion", position = 2), \
                        ApiArg("close", description="close issue", position = 3) \
                        ]
        self._command = "issue"

    def execute(self, args):
        if self.fetchParams(args):
            return

        issueId = self._params[0].getValue()
        addNote = self._params[1].getValue()
        printDiscussion = self._params[2].getValue()
        closeIssue = self._params[3].getValue()


        answer = self.requestFactory.get(self._getIssueById(issueId, False)).json()

        if closeIssue is not None:
            printer.out("Try to close issue")
            self.requestFactory.put(self._closeIssue(issueId))
            answer = self.requestFactory.get(self._getIssueById(issueId, False)).json()

        if addNote is not None:
            noteToAdd = input("Add a discussion note to issue \"{}\":\n>".format(answer["title"]))
            printer.out("Discussion note:\n\"{}\"".format(noteToAdd))

            self.requestFactory.post(self._postIssueNote(issueId), {"body": noteToAdd})

        if printDiscussion is not None:
            notes = Paginator.fetchAll(self.requestFactory, self._getIssueNotes(issueId))
            
            for note in notes:
                author = note["author"]["username"]
                body = note["body"]
                printer.out("--------\nauthor {}: {}".format(author, body))

        description = answer["description"] 
        labels = answer["labels"]
        printer.out("* Description: {}".format(description))
        printer.out("* Lables: {}".format(labels))
        printer.out("* State: {}".format(answer["state"]))

    def _postIssueNote(self, issueId):
        return self.address + "/issues/{}/notes".format(issueId)

    def _getIssueById(self, issueId, opened):
        op = ""
        if opened:
            op = "?state=opened"
        return self.address + "/issues/{}{}".format(issueId, op)

    def _closeIssue(self, issueId):
        return self.address + "/issues/{}?state_event=close".format(issueId)


    def _getIssueNotes(self, issueId):
        return self.address + "/issues/{}/notes?sort=asc".format(issueId)

class StringBuilder(object):

    def __init__(self):
        self.stub = ""

    def append(self, text):
        self.stub += "\n{}".format(text)

    def toString(self):
        return self.stub

class MergeRequestApi(Api):

    def _setup(self):
        self._params = [ApiArg("iid", description="id of MR", position = 0), \
                        ApiArg("a", description="add note", position = 1), \
                        ApiArg("d", description="print discussion", position = 2) \
                        ]
        self._command = "mr"

    def execute(self, args):
        if self.fetchParams(args):
            return

        mrId = self._params[0].getValue()

        if mrId is not None:
            self.printMergeRequest(mrId)
        else:
            self.printOpenMergeRequests()

    def printOpenMergeRequests(self):
        answer = self.requestFactory.get(self._getOpenMergeRequests()).json()
        
        rows = []
        for mr in answer:
            iid = mr["iid"]
            title = mr["title"]
            title = Utils.lineBreak(title, 30)
            sourceBranch = mr["source_branch"]
            author = mr["author"]["username"]
            workInProgress = mr["work_in_progress"]
            mergeStatus = mr["merge_status"]
            webUrl = mr["web_url"]
            upVotes = mr["upvotes"]
            userNotesCount = mr["user_notes_count"]
            row = [iid, upVotes, title, author, userNotesCount, workInProgress, mergeStatus, webUrl]
            rows.append(row)
        
        printer.out(tabulate(rows, headers=["id", "👍", "title", "auth", "n", "wip" , "status", "url"], tablefmt="simple"))

    def printMergeRequest(self, mrId):
        answer = self.requestFactory.get(self._getMergeRequest(mrId)).json()
        title = answer["title"]
        description = answer["description"]
        author = answer["author"]["username"]
        upVotes = answer["upvotes"]
        mergeStatus = answer["merge_status"]
        workInProgress = answer["work_in_progress"]
        
        printer.out("Title: {},\nDescription: {},\nAuthor: {},\nUpvotes: {},\nMR-Status: {},\nWIP: {}".format(title, description, author, upVotes, mergeStatus, workInProgress))

        discussions = Paginator.fetchAll(self.requestFactory, self._getMergeRequestDiscussion(mrId))
        for discussion in discussions:
            discussionId = discussion["id"]
            command = self.printSingleDiscussion(mrId, discussion)
            if command == "continue":
                continue
            elif command == "break":
                break
        # TODO thumbs up

    def printSingleDiscussion(self, mrId, discussion = None, discussionId = None):
        if discussionId is not None:
            discussion = self.requestFactory.get(self._getDiscussion(mrId, discussionId)).json()
        builder = StringBuilder()
        notes = discussion["notes"]
        discussionId = discussion["id"]
        sumResolved = 0
        sumResolvable = 0

        for note in notes:
            author = note["author"]["username"]
            body = note["body"]
            body = body.replace(":thumbsup:", "👍")
            if "resolved" in note:
                sumResolvable += 1
                resolved = note["resolved"]
                if resolved:
                    sumResolved += 1
            updated_at = note["updated_at"]

            prefix = "    ({}): ".format(author)
            body = self.setSpaces(body, len(prefix))
            builder.append("{}{}".format(prefix, body))

        resolvable = sumResolvable > 0 
        allResolved = sumResolved == sumResolvable
        resolveStatus = " - resolved {}".format(allResolved) if resolvable  else ""

        if resolvable:
            printer.out("\n# Discussion {}:\n{}\n".format(resolveStatus, builder.toString()))
        else:
            return "continue"
  
        user_input = input("command (a - answer, n/[space] - next discussion, s - skip all)")
        if user_input == "n" or len(user_input) == 0:
            return "continue"
        elif user_input == "a":
            answer = input("Answer: ")
            if len(answer) > 0:
                response = self.requestFactory.post(self._postAnswerDiscussion(mrId, discussionId), {"body": answer}).json()
                if "body" in response:
                    printer.out("Success:\n{}\n\n".format(response["body"]))
                    self.printSingleDiscussion(mrId, discussionId = discussionId)
                else:
                    printer.out("Error...\n\n")
        elif user_input == "s":
            return "break"

        return ""

    def setSpaces(self, text, spaces):
        spaces = [" " for i in range(spaces)]
        spaces = "".join(spaces)
        text = text.split("\n")
        for i in range(1, len(text)):
            text[i] = spaces + text[i]
        return "\n".join(text)

    def _postAnswerDiscussion(self, mrId, discussionId):
        return self.address + "/merge_requests/{}/discussions/{}/notes".format(mrId, discussionId)

    def _getDiscussion(self, mrId, discussionId):
        return self.address + "/merge_requests/{}/discussions/{}".format(mrId, discussionId)

    def _getOpenMergeRequests(self):
        return self.address + "/merge_requests?state=opened"
    
    def _getMergeRequestNotes(self, mrId):
        return self.address + "/merge_requests/{}/notes?sort=asc&order_by=updated_at".format(mrId)

    def _getMergeRequestDiscussion(self, mrId):
        return self.address + "/merge_requests/{}/discussions".format(mrId)
    
    def _getMergeRequest(self, mrId):
        return self.address + "/merge_requests/{}".format(mrId)

class BranchApi(Api):

    def _setup(self):
        self._params = [ApiArg("search"), ApiArg("id")]
        self._command = "branches"

    def execute(self, args):
        # args: id, search
        self.fetchParams(args)

        branches = self.requestFactory.get(self.api()).json()
        
        rows = []
        for branch in branches:
            name = branch["name"]
            merged = branch["merged"]
            authorName = branch["commit"]["author_name"]
            commitTitle = branch["commit"]["title"]
            commitShort = branch["commit"]["short_id"]
            row = [name, merged, authorName, commitTitle, commitShort]
            rows.append(row)

        printer.out(tabulate(rows, headers = ["name", "merged", "author", "commit", "hash"]))

    def api(self):
        return self.address + "/repository/branches{}".format(self.apiArgs())

class LabelsApi(Api):

    def _setup(self):
        self._params = [ApiArg("o", description = "operation", position = 0, required = True), \
                        ApiArg("id", description = "issue id", position = 1, required = True), \
                        ApiArg("name", description =  "label name", position = 2, required = True)]
        self._command = "lab"
        self.addHelp("Add/remove labels")

    def execute(self, args):
        if self.fetchParams(args):
            return

        operation = self._params[0].getValue()
        issueId = self._params[1].getValue()
        labelName = self._params[2].getValue()

        splitted = labelName.split(",")
        splitted = [x.strip() for x in splitted]

        if not (operation == "add" or operation == "rm"):
            return printer.out("Operation not supported {}. Supported operations: add/rm".format(operation))

        # Get labels for issue
        issueAnswer = self.requestFactory.get(self._apiGetIssueById(issueId, True)).json()
        if "labels" not in issueAnswer:
            printer.out("Failed to get labels for issue {}: {}".format(issueId, issueAnswer))
            return

        labels = issueAnswer["labels"]
        printer.out("Current labels {}".format(labels))
        if(operation == "add"):
            [labels.append(x) for x in splitted]
        elif operation == "rm":
            [labels.remove(x) for x in splitted]

        setLabelsAnswer = self.requestFactory.put(self._apiPutLabelsToIssue(issueId, labels)).json()
        if "id" not in setLabelsAnswer:
            printer.out("Failed to move issue {}".format(setLabelsAnswer))

        idFromAnswer = setLabelsAnswer["iid"]

        issueAnswer = self.requestFactory.get(self._apiGetIssueById(idFromAnswer, True)).json()
        if "id" in issueAnswer:
            title = issueAnswer["title"]
            labels = issueAnswer["labels"]
            assignees = [assignee["username"] for assignee in issueAnswer["assignees"]]
            printer.out("Issue: {}\n -> labels: {}\n -> assignees: {}".format(title, labels, assignees))

    def _apiGetIssueById(self, issueId, opened):
        op = ""
        if opened:
            op = "?state=opened"
        return self.address + "/issues/{}{}".format(issueId, op)

    def _apiPutLabelsToIssue(self, issueIid, labelsArray):
        labelsArray = [Utils.encode(e) for e in labelsArray]
        serializedLables = ",".join(labelsArray)
        return self.address + "/issues/{}?labels={}".format(issueIid, serializedLables)

class IssueMoveApi(Api):

    def _setup(self):
        self._params = [ApiArg("i", description = "issue id", position = 0, required = True), \
                        ApiArg("s", description = "source list", position = 1, required = True), \
                        ApiArg("t", description =  "target list", position = 2, required = True), \
                        ApiArg("u", description =  "username"), \
                        ApiArg("x", description = "unassign all users")]
        self._command = "move"
        self.addHelp("Move issue from list s to list t and assign to user u")

    def execute(self, args):
        if self.fetchParams(args):
            return

        issue = self._params[0].getValue()
        source = self._params[1].getValue()
        target = self._params[2].getValue()
        assignUser = self._params[3].getValue() is not None
        unassign = self._params[4].getValue() is not None

        issueIdSaved = self.moveToPanel(issue, target)
        if issueIdSaved is None:
            return
        if assignUser:
            self.assignToUser(issueIdSaved, self._params[3].getValue())
        if unassign:
            self.unassignIssue(issueIdSaved)

        issueAnswer = self.requestFactory.get(self._apiGetIssueById(issue, True)).json()
        if "id" in issueAnswer:
            title = issueAnswer["title"]
            labels = issueAnswer["labels"]
            assignees = [assignee["username"] for assignee in issueAnswer["assignees"]]
            printer.out("Issue: {}\n -> labels: {}\n -> assignees: {}".format(title, labels, assignees))


    def moveToPanel(self, issueId, labelName):
        answer = self.requestFactory.get(self._apiGetProjectBoards())
        allLabels = []
        boards = answer.json()
        for b in boards:
            lists = b["lists"]
            for list in lists:
                allLabels.append(list["label"]["name"])
            
        if labelName not in allLabels:
            printer.out("List {} not known.\nKnown lists {}".format(labelName, allLabels))
            return
        
        # Get labels for issue, remove label of old board list and add new labelName
        issueAnswer = self.requestFactory.get(self._apiGetIssueById(issueId, True)).json()
        if "labels" not in issueAnswer:
            printer.out("Failed to get labels for issue {}: {}".format(issueId, issueAnswer))
            return

        labels = issueAnswer["labels"]
        numberOfLabelsBefore = len(labels)
        for panelLabel in allLabels:
            if panelLabel in labels:
                labels.remove(panelLabel)

        
        labels.append(labelName)  
        assert numberOfLabelsBefore == len(labels)
        printer.out("Set labels {}".format(labels))
        setLabelsAnswer = self.requestFactory.put(self._apiPutLabelsToIssue(issueId, labels)).json()
        if "id" not in setLabelsAnswer:
            printer.out("Failed to move issue {}".format(setLabelsAnswer))
        return setLabelsAnswer["iid"]
            
    def assignToUser(self, issueId, userName):
        answer = self.requestFactory.get(self._apiGetUsersByName(userName))
        users = answer.json()
        
        foundUser = None
        for user in users:
            if user["username"] == userName:
                foundUser = user
                break

        if foundUser is None:
            printer.out("User not found: '{}' registered?".format(userName))
            return
        
        assignAnswer = self.requestFactory.put(self._apiPutAssignIssue(issueId, foundUser["id"])).json()
        if "id" not in assignAnswer:
            printer.out("Failed to assign issue {}".format(assignAnswer))
    
    def unassignIssue(self, issueId):
        answer = self.requestFactory.put(self._apiPutAssignIssue(issueId, "0")).json()
        if "id" not in answer:
            printer.out("Failed to unassign {}".format(answer))


    def _apiGetProjectBoards(self):
       return self.address + "/boards"

    def _apiGetIssueById(self, issueId, opened):
        op = ""
        if opened:
            op = "?state=opened"
        return self.address + "/issues/{}{}".format(issueId, op)

    def _apiPutLabelsToIssue(self, issueIid, labelsArray):
        labelsArray = [Utils.encode(e) for e in labelsArray]
        serializedLables = ",".join(labelsArray)
        return self.address + "/issues/{}?labels={}".format(issueIid, serializedLables)

    def _apiGetUsersByName(self, userName):
        return self.address + "/users?username={}".format(userName)

    def _apiPutAssignIssue(self, issueId, userId):
        return self.address + "/issues/{}?assignee_ids={}".format(issueId, userId)


class BoardApi(Api):

    def _setup(self):
        self._params = [ApiArg("list", description = "list name", position = 0), \
                        ApiArg("u", description = "username", position = 1)]
        self._command = "board"

    def execute(self, args):
        if self.fetchParams(args):
            return

        printList = self._params[0].getValue()
        if printList:
            self._printList(self._params[0].getValue(), self._params[1].getValue())
        else:
            self.printBoard()

    def _printList(self, labelName, username = None):
        issues = Paginator.fetchAll(self.requestFactory, self._apiGetIssueWithLabels([labelName]))
        
        issueRows = []
        for issue in issues:
            issueId = issue["iid"]
            issueTitle = issue["title"]
            issueLabels = issue["labels"]
            issueAssigns = issue["assignee"]
            if issueAssigns is not None:
                issueAssigns = issue["assignee"]["username"]

            if username is not None:
                if username != issueAssigns:
                    continue
            issueRows.append([issueId, issueTitle, issueLabels, issueAssigns])
            
        printer.out(tabulate(issueRows, headers=['id', 'title', 'labels', 'assigned to']))


    def _apiGetIssueWithLabels(self, labels):
        labels = ",".join(labels)
        return self.address + "/issues?labels={}&state=opened".format(labels)

    def printBoard(self):
        boards = self.requestFactory.get(self._apiBoard()).json()

        for board in boards:
            lists = board["lists"]
            boardTable = []
            maxSize = 0
            listNames = []
            for listItem in lists:
                listName = listItem["label"]["name"]
                listNames.append(listName)
                issueList = self.getIssuesByLabel(listName)
                boardTable.append(issueList)
                if len(issueList) > maxSize:
                    maxSize = len(issueList)
            rows = []
            for i in range(maxSize):
                row = []
                for column in boardTable:
                    if len(column) > i:
                        row.append(Util.lineBreak(column[i], 30))
                    else:
                        row.append("-")
                rows.append(row)
            printer.out("----------\nBoard: {}\n----------".format(board["id"]))
            printer.out(tabulate(rows, headers = listNames))

    def getIssuesByLabel(self, labelName):
        issues = self.requestFactory.get(self.address + "/issues?labels={}".format(labelName)).json()
        issues = ["({}): {}".format(issue["id"], issue["title"]) for issue in issues]
        return issues

    def _apiBoard(self):
        return self.address + "/boards"


class Command(object):
    
    def __init__(self, gitlab, apis):
        self.executer = gitlab
        self.apis = apis
        
    def translate(self, args):
        if len(args) < 2:
            print("\nNo command given\n")
            self.overview()
            return
        c = args[1]
        r = args[2:len(args)]
        self.mapCommand(c, r)
    
    def mapCommand(self, command, args):
        if command == "assign":
            assert len(args) >= 2, "assign #issue #username"
            self.executer.assignToUser(args[0], args[1])
        elif command == "unassign":
            assert len(args) >= 1, "unassign #issueId"
            self.executer.unassignIssue(args[0])
        elif command == "mv":
            assert len(args) >= 2, "mv #issue #labelname"
            self.executer.moveToPanel(args[0], args[1])
        elif command == "delready":
            assert len(args) >= 1, "delready #listname"
            self.executer.removeReadyLabel(args[0])
        elif command == "-h" or command == "help":
            self.overview()
        elif self.mapApi(command, args):
            print("\n")
        else:
            printer.out("Command not supplied: {}\n\n".format(command))
            self.overview()


    def mapApi(self, command, args):
        for api in self.apis:
            if api.match(command):
                api.execute(args)
                return True
        return False
            
    def overview(self):
        c = "Help\n\n"
        c += "#.. required parameter\n"
        c += "?.. optional parameter\n\n"
        c += "-h/help\n"
        c += "assign #issue #username - assign #issue to #username\n"
        c += "unassign #issueId  - unassign all users from #issueId \n"
        c += "mv #issue #labelname  - set #labelname to #issue\n"
        c += "delready #listname  - remove Ready label from list #listname \n"
        print(c)
        for api in self.apis:
            api.help()



printer = Printer()
main(sys.argv)
