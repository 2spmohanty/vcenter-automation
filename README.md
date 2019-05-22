# vCenter Automation :  Rest In Peak

The Plan is to create an Automation Platform that could handle Automation of vCenter Tasks in a Large scale from anywhere. 
The Rest In Peak Application provides a subtle way of Automation. It gives a friendly UI for the UI lovers while it also exposes REST endpoints for those who like to handle automation by writing codes.
This application can be used to trigger Automation on Multiple vCenters simultaneously.

Morever it can be deployed anywhere as the application image is hosted on Docker Hub.


## Phillosophy

vCenter Automation from Anywhere , Everywhere.

## Stack

- Web2py Framework
- PyVmomi
- Postgres DB

## Future Works

- vSAN Automation.
- NSX-T Automation.
- Host Level Operations.
- VM Level Operations (As of now only Power and Clone is covered)
- DC Level Operation.

## How to Run.

Put Two Nodes in Swarm Mode.

And in Master Node download the `docker-compose.yaml` file.

`docker stack deploy -c docker-compose.yml app`

#### Home Page

![Home Page](https://raw.githubusercontent.com/2spmohanty/vcenter-automation/master/Images/HomePage.png)

#### Operation Page

###### Operation can be triggered from the UI.

![VM Power Ops](https://raw.githubusercontent.com/2spmohanty/vcenter-automation/master/Images/Page_Explanation.png)

![Trigger Ops UI](https://raw.githubusercontent.com/2spmohanty/vcenter-automation/master/Images/Triggering_Ops_UI.png)

###### Operation can be triggered from a Rest Client Such as Post Man.

![Postman](https://raw.githubusercontent.com/2spmohanty/vcenter-automation/master/Images/Postman.png)

#### Result Page

After an Operation is Triggered the user is directed to a result page which is dynamically refreshed keeping the user updated about the current status of operation. In case the Operation is triggered from a REST client the output is the URL of the result page.

![Result](https://raw.githubusercontent.com/2spmohanty/vcenter-automation/master/Images/Result_External_Client.png)


### Support or Contact

2spmmohanty at gmail dot com

Please open issues in this branch if you would like to enable any other features


### Special Thanks

Web2Py Framework : This Framewrok serves the backbone of UI of this appliaction. I thank the Web2py Framework community for all the help and support that they have provided.
