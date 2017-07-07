var SafeMath = artifacts.require("SafeMath");
var Set = artifacts.require("ItSet");
var ECV = artifacts.require("ECVerify");
var TL = artifacts.require("Trustline");
var IR = artifacts.require("Interests");
var Fees = artifacts.require("Fees");
var CN = artifacts.require("CurrencyNetwork");

module.exports = function(deployer) {
  deployer.deploy(SafeMath);
  deployer.deploy(Set);
  deployer.deploy(ECV);
  deployer.deploy(TL);
  deployer.deploy(IR);
  deployer.deploy(Fees);
  deployer.link(SafeMath, CN);
  deployer.link(Set, CN);
  deployer.link(ECV, CN);
  deployer.link(TL, CN);
  deployer.link(IR, CN);
  deployer.link(Fees, CN);
  deployer.deploy(CN, "EUR", "E");
};
