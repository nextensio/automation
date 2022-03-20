package main

import (
	"context"
	"crypto/tls"
	"fmt"
	"io/ioutil"
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

var bundle1attrjson = map[string]interface{}{"bid": CNCTR3, "dept": []string{"ABU", "BBU"},
	"team": []string{"engineering", "sales"}, "IC": 1, "manager": 1, "nonemployee": "allow"}
var bundle2attrjson = map[string]interface{}{"bid": CNCTR1, "dept": []string{"ABU", "BBU"},
	"team": []string{"engineering", "sales"}, "IC": 1, "manager": 1, "nonemployee": "allow"}
var bundle3attrjson = map[string]interface{}{"bid": CNCTR2, "dept": []string{"ABU", "BBU"},
	"team": []string{"engineering", "sales"}, "IC": 1, "manager": 1, "nonemployee": "allow"}
var bundle4attrjson = map[string]interface{}{"bid": CNCTR4, "dept": []string{"ABU", "BBU"},
	"team": []string{"engineering", "sales"}, "IC": 1, "manager": 1, "nonemployee": "allow"}

var host1attrjson = map[string]interface{}{"host": "kismis.org",
	"routeattrs": []map[string]interface{}{
		{"tag": "v2", "team": []string{"engineering"}, "dept": []string{"ABU", "BBU"},
			"category": []string{"employee", "nonemployee"}, "type": []string{"IC", "manager"},
			"IClvl": 1, "mlvl": 1,
		},
		{"tag": "v1", "team": []string{"sales"}, "dept": []string{"BBU", "ABU"},
			"category": []string{"employee"}, "type": []string{"manager", "IC"},
			"IClvl": 4, "mlvl": 4,
		}},
}

var host2attrjson = map[string]interface{}{"host": "nextensio-default-internet",
	"routeattrs": []map[string]interface{}{
		{"tag": "", "team": []string{""}, "dept": []string{""},
			"category": []string{""}, "type": []string{""},
			"IClvl": 0, "mlvl": 0,
		},
	},
}

var tracereq1json = map[string]interface{}{"traceid": "CaliforniaLinuxUsers", "uid": "", "category": []string{""}, "type": []string{""},
	"iclevel": 50, "mgrlevel": 50, "dept": []string{""}, "team": []string{""},
	"location": "California", "ostype": "Linux", "osver": 0.0,
}
var tracereq2json = map[string]interface{}{"traceid": "SalesEmployees", "uid": "", "category": []string{"employee"}, "type": []string{""},
	"iclevel": 50, "mgrlevel": 50, "dept": []string{""}, "team": []string{"sales"},
	"location": "", "ostype": "", "osver": 0.0,
}

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

func read_rune(file string) []rune {
	content, err := ioutil.ReadFile(file)
	for err != nil {
		fmt.Println("Cant read file", file)
		time.Sleep(1 * time.Second)
		content, err = ioutil.ReadFile(file)
	}
	str := string(content)
	return []rune(str)
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
		fmt.Println("Gateway creation failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddGateway(ctx, apis.GatewayStruct{Name: GW1}, "superadmin")
	}
	ok, resp, err = client.DefaultApi.AddGateway(ctx, apis.GatewayStruct{Name: GW2}, "superadmin")
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Gateway creation failed, retrying ...")
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

	ok, resp, err = client.DefaultApi.AddBundle(ctx,
		apis.BundleStruct{Bid: CNCTR3, Name: "Default Internet", Services: []string{"nextensio-default-internet"}, Gateway: GW2, Cpodrepl: 2},
		"superadmin", TENANT,
	)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add Bundle failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddBundle(ctx,
			apis.BundleStruct{Bid: CNCTR3, Name: "Default Internet", Services: []string{"nextensio-default-internet"}, Gateway: GW2, Cpodrepl: 2},
			"superadmin", TENANT,
		)
	}
	ok, resp, err = client.DefaultApi.AddBundleAttr(ctx, bundle1attrjson, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add battr failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddBundleAttr(ctx, bundle1attrjson, "superadmin", TENANT)
	}

	ok, resp, err = client.DefaultApi.AddBundle(ctx,
		apis.BundleStruct{Bid: CNCTR1, Name: "Kismis ONE", Services: []string{"v1.kismis.org"}, Gateway: GW2, Cpodrepl: 2},
		"superadmin", TENANT,
	)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add Bundle failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddBundle(ctx,
			apis.BundleStruct{Bid: CNCTR1, Name: "Kismis ONE", Services: []string{"v1.kismis.org"}, Gateway: GW2, Cpodrepl: 2},
			"superadmin", TENANT,
		)
	}
	ok, resp, err = client.DefaultApi.AddBundleAttr(ctx, bundle2attrjson, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add battr failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddBundleAttr(ctx, bundle2attrjson, "superadmin", TENANT)
	}

	ok, resp, err = client.DefaultApi.AddBundle(ctx,
		apis.BundleStruct{Bid: CNCTR2, Name: "Kismis TWO", Services: []string{"v2.kismis.org"}, Gateway: GW2, Cpodrepl: 2},
		"superadmin", TENANT,
	)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add Bundle failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddBundle(ctx,
			apis.BundleStruct{Bid: CNCTR2, Name: "Kismis TWO", Services: []string{"v2.kismis.org"}, Gateway: GW2, Cpodrepl: 2},
			"superadmin", TENANT,
		)
	}
	ok, resp, err = client.DefaultApi.AddBundleAttr(ctx, bundle3attrjson, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add battr failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddBundleAttr(ctx, bundle3attrjson, "superadmin", TENANT)
	}

	ok, resp, err = client.DefaultApi.AddBundle(ctx,
		apis.BundleStruct{Bid: CNCTR4, Name: "Connector To Connector", Services: []string{}, Gateway: GW2, Cpodrepl: 1},
		"superadmin", TENANT,
	)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add Bundle failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddBundle(ctx,
			apis.BundleStruct{Bid: CNCTR4, Name: "Connector To Connector", Services: []string{}, Gateway: GW2, Cpodrepl: 1},
			"superadmin", TENANT,
		)
	}
	ok, resp, err = client.DefaultApi.AddBundleAttr(ctx, bundle4attrjson, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add battr failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddBundleAttr(ctx, bundle4attrjson, "superadmin", TENANT)
	}

	ok, resp, err = client.DefaultApi.AddHostAttr(ctx, host1attrjson, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add hostattr failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddHostAttr(ctx, host1attrjson, "superadmin", TENANT)
	}

	ok, resp, err = client.DefaultApi.AddHostAttr(ctx, host2attrjson, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add hostattr failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddHostAttr(ctx, host2attrjson, "superadmin", TENANT)
	}

	ok, resp, err = client.DefaultApi.AddTraceReq(ctx, tracereq1json, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add tracereq failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddTraceReq(ctx, tracereq1json, "superadmin", TENANT)
	}
	ok, resp, err = client.DefaultApi.AddTraceReq(ctx, tracereq2json, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add tracereq failed, retrying ...")
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddTraceReq(ctx, tracereq2json, "superadmin", TENANT)
	}

	r := read_rune("../policy.AccessPolicy")
	ok, resp, err = client.DefaultApi.AddPolicyHandler(ctx, apis.AddPolicy{Pid: "AccessPolicy", Rego: r}, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add policy failed, retrying ...", err, resp, ok)
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddPolicyHandler(ctx, apis.AddPolicy{Pid: "AccessPolicy", Rego: r}, "superadmin", TENANT)
	}

	r = read_rune("../policy.RoutePolicy")
	ok, resp, err = client.DefaultApi.AddPolicyHandler(ctx, apis.AddPolicy{Pid: "RoutePolicy", Rego: r}, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add policy failed, retrying ...", err, resp, ok)
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddPolicyHandler(ctx, apis.AddPolicy{Pid: "RoutePolicy", Rego: r}, "superadmin", TENANT)
	}

	r = read_rune("../policy.TracePolicy")
	ok, resp, err = client.DefaultApi.AddPolicyHandler(ctx, apis.AddPolicy{Pid: "TracePolicy", Rego: r}, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add policy failed, retrying ...", err, resp, ok)
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddPolicyHandler(ctx, apis.AddPolicy{Pid: "TracePolicy", Rego: r}, "superadmin", TENANT)
	}

	r = read_rune("../policy.StatsPolicy")
	ok, resp, err = client.DefaultApi.AddPolicyHandler(ctx, apis.AddPolicy{Pid: "StatsPolicy", Rego: r}, "superadmin", TENANT)
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add policy failed, retrying ...", err, resp, ok)
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddPolicyHandler(ctx, apis.AddPolicy{Pid: "StatsPolicy", Rego: r}, "superadmin", TENANT)
	}

	r = read_rune("../../../testCert/nextensio.crt")
	ok, resp, err = client.DefaultApi.AddCerts(ctx, apis.CertStruct{Certid: "CACert", Cert: r}, "superadmin")
	for err != nil || (resp != nil && resp.StatusCode != 200) || ok.Result != "ok" {
		fmt.Println("Add cert failed, retrying ...", err, resp, ok)
		time.Sleep(1 * time.Second)
		ok, resp, err = client.DefaultApi.AddCerts(ctx, apis.CertStruct{Certid: "CACert", Cert: r}, "superadmin")
	}

	fmt.Println("APIs completed succesfully")
}
