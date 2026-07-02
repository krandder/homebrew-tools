class ClaudeBroker < Formula
  desc "Install/run the transparent Claude OAuth refresh broker on a follower"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-broker"
  version "1.3.1"
  sha256 "e4265285f247d3bda4cfcb3e5fee4c18352bfbde7ac1e8600b3cc136c41a36ee"
  depends_on "claude-broker-proxy"
  def install
    bin.install "claude-broker"
  end
  test do
    assert_predicate bin/"claude-broker", :exist?
  end
end
