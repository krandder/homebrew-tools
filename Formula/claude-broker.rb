class ClaudeBroker < Formula
  desc "Install/run the transparent Claude OAuth refresh broker on a follower"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-broker"
  version "1.4.0"
  sha256 "5642d5d3286c8a43271708d4f5177e38e2e927f6dc0869e1a0651ba932f151c3"
  depends_on "claude-broker-proxy"
  def install
    bin.install "claude-broker"
  end
  test do
    assert_predicate bin/"claude-broker", :exist?
  end
end
