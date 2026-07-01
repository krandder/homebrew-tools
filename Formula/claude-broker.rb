class ClaudeBroker < Formula
  desc "Install/run the transparent Claude OAuth refresh broker on a follower"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/claude-broker"
  version "1.0.0"
  sha256 "808ba7b5b01b0e30ea51494e7c580b8b27ab2d7c615b50669f485e05c9797d1d"
  depends_on "claude-broker-proxy"
  def install
    bin.install "claude-broker"
  end
  test do
    assert_predicate bin/"claude-broker", :exist?
  end
end
