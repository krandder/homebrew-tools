class ClaudeBrokerProxy < Formula
  desc "Local transparent proxy routing Claude Code OAuth refresh to the leader broker"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-broker-proxy"
  version "1.1.0"
  sha256 "6379674864b698f6251794598ceea0bfe2cb1140c4b24bae184d2ebc198dffdb"
  depends_on "python@3.11"
  def install
    bin.install "claude-broker-proxy"
  end
  test do
    assert_predicate bin/"claude-broker-proxy", :exist?
  end
end
