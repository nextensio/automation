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
		ok, resp, err = client.DefaultApi.AddClientid(ctx, apis.AddClientId{Clientid: "0oaz5lndczD0DSUeh4x6"}, "superadmin")
	}

	ok, resp, err = client.DefaultApi.AddGateway(ctx, apis.GatewayStruct{Name: GW1}, "superadmin")
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Clientid creation failed, retrying ...")
		ok, resp, err = client.DefaultApi.AddGateway(ctx, apis.GatewayStruct{Name: GW1}, "superadmin")
	}
	ok, resp, err = client.DefaultApi.AddGateway(ctx, apis.GatewayStruct{Name: GW2}, "superadmin")
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Clientid creation failed, retrying ...")
		ok, resp, err = client.DefaultApi.AddGateway(ctx, apis.GatewayStruct{Name: GW2}, "superadmin")
	}

	ok, resp, err = client.DefaultApi.AddTenant(ctx, apis.TenantUpdate{Id: TENANT, Name: TENANT}, "superadmin")
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Tenant creation failed, retrying ...")
		ok, resp, err = client.DefaultApi.AddTenant(ctx, apis.TenantUpdate{Id: TENANT, Name: TENANT}, "superadmin")
	}

	ok, resp, err = client.DefaultApi.AddClusterHandler(ctx,
		apis.TenantCluster{Gateway: GW1, Image: "registry.gitlab.com/nextensio/cluster/minion:latest", Apodsets: 2, Apodrepl: 1},
		"superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Tenant creation failed, retrying ...")
		ok, resp, err = client.DefaultApi.AddClusterHandler(ctx,
			apis.TenantCluster{Gateway: GW1, Image: "registry.gitlab.com/nextensio/cluster/minion:latest", Apodsets: 2, Apodrepl: 1},
			"superadmin", TENANT)
	}

	ok, resp, err = client.DefaultApi.AddClusterHandler(ctx,
		apis.TenantCluster{Gateway: GW2, Image: "registry.gitlab.com/nextensio/cluster/minion:latest", Apodsets: 1, Apodrepl: 1},
		"superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Tenant creation failed, retrying ...")
		ok, resp, err = client.DefaultApi.AddClusterHandler(ctx,
			apis.TenantCluster{Gateway: GW2, Image: "registry.gitlab.com/nextensio/cluster/minion:latest", Apodsets: 1, Apodrepl: 1},
			"superadmin", TENANT)
	}
	fmt.Println("APIs completed succesfully")
}
