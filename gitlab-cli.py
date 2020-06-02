#!/usr/bin/env python
# coding: utf-8


import os
import requests 
import urllib
import datetime
import sys
import json
from tabulate import tabulate


def main(args):
    d = createDeligator()
    d.translate(args)
    
def createDeligator():
    configuration = Configuration()
    requestFactory = RequestFactory(configuration)
    resources = GitlabResources(configuration)
    executor = GitLab(requestFactory, resources)
    
    return Command(executor)


class Configuration(object):
    
    def __init__(self):
        with open("./configuration.json", "r") as file:
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


class GitlabResources(object):
    
    def __init__(self, configuration):
        self.address = "{}/api/{}/projects/{}".format(configuration.getHostAddress(),                                                      configuration.getApiVersion(),                                                      configuration.getProjectId())

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


    def getUsersByName(self, userName):
        return self.address + "/users?username={}".format(userName)

    def putAssignIssue(self, issueId, userId):
        return self.address + "/issues/{}?assignee_ids={}".format(issueId, userId)
    
    def getPipelinesByUsername(self, username):
        return self.address + "/pipelines?username={}".format(username)
    
    def getPipelines(self):
        return self.address + "/pipelines"
    
    def getProjectBoards(self):
        return self.address + "/boards"
    
    def getOpenMergeRequests(self):
        return self.address + "/merge_requests?state=opened"
    
    def getMergeRequestNotes(self, mrId):
        return self.address + "/merge_requests/{}/notes?sort=asc&order_by=updated_at".format(mrId)
    
    def getMergeRequest(self, mrId):
        return self.address + "/merge_requests/{}".format(mrId)
    
    def getIssueNotes(self, issueId):
        return self.address + "/issues/{}/notes?sort=asc".format(issueId)


class RequestFactory(object):

    def __init__(self, configuration):
        self.config = configuration

    def get(self, endpoint):
        print(endpoint)
        r = requests.get(url = endpoint,                headers = {'private-token': '{}'.format(self.config.getToken())})
        return r

    def post(self, endpoint, requestData):
        r = requests.post(url = endpoint, data = urllib.parse.urlencode(requestData),         headers = {'private-token': '{}'.format(self.config.getToken())})
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
        print("Set labels {}".format(labels))
        answer = self.requestFactory.put(self.res.putLabelsToIssue(issueId, labels))
        print(answer.json())
            
    def printTodos(self):
        self.printPanel("Todo")
        
    def printWork(self):
        self.printPanel("Work")
        
    def printPanel(self, labelName, username = None):
        answer = self.requestFactory.get(self.res.getIssueWithLabels([labelName]))
        issues = answer.json()
        
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
            
        print(tabulate(issueRows, headers=['id', 'title', 'labels', 'assigned to']))
        
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
        
    def printPipelines(self, username = None):
        if username is not None:
            answer = self.requestFactory.get(self.res.getPipelinesByUsername(username))
        else:
            answer = self.requestFactory.get(self.res.getPipelines())

        pipelines = answer.json()
        rows = []
        for pip in pipelines:
            pipId = pip["id"]
            pipStatus = pip["status"]
            pipRef = pip["ref"]
            pipUrl = pip["web_url"]
            rows.append([pipId, pipStatus, pipRef, pipUrl])
        print(tabulate(rows, headers=['id', 'status', 'ref', 'url']))
        
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
            rows.append([iid, upVotes, title, author, userNotesCount, workInProgress, mergeStatus, webUrl])
        
        print(tabulate(rows, headers=["id", "upVotes", "title", "author", "notes", "wip" , "status", "url"], tablefmt="github"))
        
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
        for i in range(len(text)):
            if i > 0 and i % chars == 0:
                text = text[0:i] + "\n" + text[i:len(text)]
                
        return text
    
    def printIssue(self, issueId):
        answer = self.requestFactory.get(self.res.getIssueById(issueId, False)).json()
        description = answer["description"]
        
        notes = self.requestFactory.get(self.res.getIssueNotes(issueId)).json()
        for note in notes:
            author = note["author"]["username"]
            body = note["body"]
            print("--------\nauthor {}: {}".format(author, body))
    


class Command(object):
    
    def __init__(self, gitlab):
        self.executer = gitlab
        
    def translate(self, args):
        c = args[1]
        r = args[2:len(args)]
        self.mapCommand(c, r)
    
    def mapCommand(self, command, args):
        if command == "list":
            assert len(args) >= 1, "list #labelname ?username"
            if len(args) >= 2:
                self.executer.printPanel(args[0], args[1])
            else:
                self.executer.printPanel(args[0])
        elif command == "assign":
            assert len(args) >= 2, "assign #issue #username"
            self.executer.assignToUser(args[0], args[1])
        elif command == "unassign":
            assert len(args) >= 1, "unassign #issueId"
            self.executer.unassignIssue(args[0])
        elif command == "pipes":
            if len(args) >= 1:
                self.executer.printPipelines(args[0])
            else:
                self.executer.printPipelines()
        elif command == "mv":
            assert len(args) >= 2, "mv #issue #labelname"
            self.executer.moveToPanel(args[0], args[1])
        elif command == "delready":
            assert len(args) >= 1, "delready #listname"
            self.executer.removeReadyLabel(args[0])
        elif command == "mr":
            if len(args) >= 1:
                self.executer.printMergeRequest(args[0])
            else:
                self.executer.printOpenMergeRequests()
        elif command == "issue":
            assert len(args) >= 1, "issue #issueId"
            self.executer.printIssue(args[0])
        elif command == "-h" or command == "help":
            self.overview()
        else:
            print("Command not supplied: {}\n\n".format(command))
            self.overview()
            
    def overview(self):
        c = "Help\n\n"
        c += "#.. required parameter\n"
        c += "?.. optional parameter\n\n"
        c += "-h/help\n"
        c += "list #labelname ?username  - list issues with #labelname by ?username \n"
        c += "assign #issue #username - assign #issue to #username\n"
        c += "unassign #issueId  - unassign all users from #issueId \n"
        c += "pipes #username  - list pipelines by #username\n"
        c += "mv #issue #labelname  - set #labelname to #issue\n"
        c += "delready #listname  - remove Ready label from list #listname \n"
        c += "mr ?mergeRequestId - (1) list all open merge requests. (2) show merge request with ?mergeRequestId\n"
        print(c)



main(sys.argv)

