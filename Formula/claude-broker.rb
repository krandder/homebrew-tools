class ClaudeBroker < Formula
  desc "Install/run the transparent Claude OAuth refresh broker on a follower"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-broker"
  version "1.1.0"
  sha256 "d7ecad287df71db2fdf2c1658acc5c40d775efe826fc1940e16c81b78fbc8093"
  depends_on "claude-broker-proxy"
  def install
    bin.install "claude-broker"
  end
  test do
    assert_predicate bin/"claude-broker", :exist?
  end
end
