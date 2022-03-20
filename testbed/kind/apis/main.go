package main

import (
	"context"
	"crypto/tls"
	"fmt"
	"net/http"
	"os"
	"time"

	apis "gitlab.com/nextensio/apis/controller/go"
)

var ctx context.Context
var client *apis.APIClient

const GW1 = "gatewaytesta.nextensio.net"
const GW2 = "gatewaytestc.nextensio.net"
const TENANT = "nextensio"
const USER1 = "test1@nextensio.net"
const USER2 = "test2@nextensio.net"
const CNCTR1 = "v1kismis"
const CNCTR2 = "v2kismis"
const CNCTR3 = "default"
const CNCTR4 = "conn2conn"

var userattrsetjson = []apis.AttrSetStruct{
	{
		Name: "category", AppliesTo: "Users", Type_: "String", IsArray: "false",
	},
	{
		Name: "type", AppliesTo: "Users", Type_: "String", IsArray: "false",
	},
	{
		Name: "level", AppliesTo: "Users", Type_: "Number", IsArray: "false",
	},
	{
		Name: "dept", AppliesTo: "Users", Type_: "String", IsArray: "true",
	},
	{
		Name: "team", AppliesTo: "Users", Type_: "String", IsArray: "true",
	},
	{
		Name: "location", AppliesTo: "Users", Type_: "String", IsArray: "false",
	},
	{
		Name: "ostype", AppliesTo: "Users", Type_: "String", IsArray: "false",
	},
	{
		Name: "osver", AppliesTo: "Users", Type_: "Number", IsArray: "false",
	},
}

var bundleattrsetjson = []apis.AttrSetStruct{
	{
		Name: "dept", AppliesTo: "Bundles", Type_: "String", IsArray: "true",
	},
	{
		Name: "team", AppliesTo: "Bundles", Type_: "String", IsArray: "true",
	},
	{
		Name: "IC", AppliesTo: "Bundles", Type_: "Number", IsArray: "false",
	},
	{
		Name: "manager", AppliesTo: "Bundles", Type_: "Number", IsArray: "false",
	},
	{
		Name: "nonemployee", AppliesTo: "Bundles", Type_: "String", IsArray: "false",
	},
}

var hostattrsetjson = []apis.AttrSetStruct{
	{Name: "dept", AppliesTo: "Hosts", Type_: "String", IsArray: "true"},
	{Name: "team", AppliesTo: "Hosts", Type_: "String", IsArray: "true"},
	{Name: "IClvl", AppliesTo: "Hosts", Type_: "Number", IsArray: "false"},
	{Name: "mlvl", AppliesTo: "Hosts", Type_: "Number", IsArray: "false"},
	{Name: "category", AppliesTo: "Hosts", Type_: "String", IsArray: "true"},
	{Name: "type", AppliesTo: "Hosts", Type_: "String", IsArray: "true"},
}

var user1attrjson = map[string]interface{}{"uid": USER1, "category": "employee",
	"type": "IC", "level": 50, "dept": []string{"ABU", "BBU"}, "team": []string{"engineering"},
	"location": "California", "ostype": "Linux", "osver": 20.04}

var user2attrjson = map[string]interface{}{"uid": USER2, "category": "employee",
	"type": "IC", "level": 50, "dept": []string{"ABU", "BBU"}, "team": []string{"sales"},
	"location": "Massachusets", "ostype": "Windows", "osver": 10.12}

func is_controller_up() bool {
	_, resp, err := client.DefaultApi.GetTenants(ctx, "superadmin")
	if err != nil || resp == nil {
		fmt.Println("Error calling APIs", err)
		return false
	}
	if resp.StatusCode != 200 {
		fmt.Println("Bad response code", resp.StatusCode)
		return false
	}
	return true
}

func create_attrset_many(sets []apis.AttrSetStruct) {
	for _, a := range sets {
		ok, resp, err := client.DefaultApi.AddAttrSet(ctx, a, "superadmin", TENANT)
		for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
			fmt.Println("Create attrset failed, retrying ..", ok, resp, err)
			time.Sleep(1 * time.Second)
			ok, resp, err = client.DefaultApi.AddAttrSet(ctx, a, "superadmin", TENANT)
		}
	}
}

func main() {
	tokens := authenticate("https://dev-635657.okta.com")
	if tokens == nil {
		os.Exit(1)
	}

	http.DefaultTransport.(*http.Transport).TLSClientConfig = &tls.Config{InsecureSkipVerify: true}
	ctx = context.WithValue(context.Background(), apis.ContextAccessToken, tokens.AccessToken)
	client = apis.NewAPIClient(apis.NewConfiguration())

	for !is_controller_up() {
		fmt.Println("Controller not up, waiting ...")
		time.Sleep(5 * time.Second)
	}

	ok, resp, err := client.DefaultApi.AddClientid(ctx, apis.AddClientId{Clientid: "0oaz5lndczD0DSUeh4x6"}, "superadmin")
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Clientid creation failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddClientid(ctx, apis.AddClientId{Clientid: "0oaz5lndczD0DSUeh4x6"}, "superadmin")
	}

	ok, resp, err = client.DefaultApi.AddGateway(ctx, apis.GatewayStruct{Name: GW1}, "superadmin")
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Clientid creation failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddGateway(ctx, apis.GatewayStruct{Name: GW1}, "superadmin")
	}
	ok, resp, err = client.DefaultApi.AddGateway(ctx, apis.GatewayStruct{Name: GW2}, "superadmin")
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Clientid creation failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddGateway(ctx, apis.GatewayStruct{Name: GW2}, "superadmin")
	}

	ok, resp, err = client.DefaultApi.AddTenant(ctx, apis.TenantUpdate{Id: TENANT, Name: TENANT}, "superadmin")
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Tenant creation failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddTenant(ctx, apis.TenantUpdate{Id: TENANT, Name: TENANT}, "superadmin")
	}

	ok, resp, err = client.DefaultApi.AddClusterHandler(ctx,
		apis.TenantCluster{Gateway: GW1, Image: "registry.gitlab.com/nextensio/cluster/minion:latest", Apodsets: 2, Apodrepl: 1},
		"superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Tenant creation failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddClusterHandler(ctx,
			apis.TenantCluster{Gateway: GW1, Image: "registry.gitlab.com/nextensio/cluster/minion:latest", Apodsets: 2, Apodrepl: 1},
			"superadmin", TENANT)
	}

	ok, resp, err = client.DefaultApi.AddClusterHandler(ctx,
		apis.TenantCluster{Gateway: GW2, Image: "registry.gitlab.com/nextensio/cluster/minion:latest", Apodsets: 1, Apodrepl: 1},
		"superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Tenant creation failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddClusterHandler(ctx,
			apis.TenantCluster{Gateway: GW2, Image: "registry.gitlab.com/nextensio/cluster/minion:latest", Apodsets: 1, Apodrepl: 1},
			"superadmin", TENANT)
	}

	create_attrset_many(userattrsetjson)
	create_attrset_many(bundleattrsetjson)
	create_attrset_many(hostattrsetjson)

	ok, resp, err = client.DefaultApi.AddUser(ctx, apis.UserAdd{Uid: USER1, Name: USER1, Pod: 1, Gateway: GW1}, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add user failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddUser(ctx, apis.UserAdd{Uid: USER1, Name: USER1, Pod: 1, Gateway: GW1}, "superadmin", TENANT)
	}
	ok, resp, err = client.DefaultApi.AddUserAttr(ctx, user1attrjson, "superadmin", TENANT, USER1)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add userattr failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddUserAttr(ctx, user1attrjson, "superadmin", TENANT, USER1)
	}

	ok, resp, err = client.DefaultApi.AddUser(ctx, apis.UserAdd{Uid: USER2, Name: USER2, Pod: 2, Gateway: GW1}, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add user failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddUser(ctx, apis.UserAdd{Uid: USER2, Name: USER2, Pod: 2, Gateway: GW1}, "superadmin", TENANT)
	}
	ok, resp, err = client.DefaultApi.AddUserAttr(ctx, user2attrjson, "superadmin", TENANT, USER2)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add userattr failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddUserAttr(ctx, user2attrjson, "superadmin", TENANT, USER2)
	}

	fmt.Println("APIs completed succesfully")
}
