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

	fmt.Println("APIs completed succesfully")
}
