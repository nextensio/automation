package main

import (
	"context"
	"crypto/tls"
	"fmt"
	"net/http"
	"os"

	apis "gitlab.com/nextensio/apis/controller/go"
)

func main() {
	tokens := authenticate("https://dev-635657.okta.com")
	if tokens == nil {
		os.Exit(1)
	}
	fmt.Println(tokens.AccessToken)

	http.DefaultTransport.(*http.Transport).TLSClientConfig = &tls.Config{InsecureSkipVerify: true}
	ctx := context.WithValue(context.Background(), apis.ContextAccessToken, tokens.AccessToken)
	// create the API client
	client := apis.NewAPIClient(apis.NewConfiguration())
	tenants, resp, err := client.DefaultApi.GetTenants(ctx, "superadmin")
	if err != nil || resp == nil {
		fmt.Println("Error calling APIs", err)
		return
	}
	if resp.StatusCode != 200 {
		fmt.Println("Bad response code", resp.StatusCode)
		return
	}
	fmt.Println(tenants)
}
