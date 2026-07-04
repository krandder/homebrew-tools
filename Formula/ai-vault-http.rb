class AiVaultHttp < Formula
  desc "HTTPS front-end for ai-vault (bearer-token auth, ACL-gated push/pull)"
  homepage "https://github.com/krandder/homebrew-tools"
  url "https://raw.githubusercontent.com/krandder/homebrew-tools/main/ai-vault-http"
  version "1.1.1"
  sha256 "f73d3ec4e718a462e70ed4cfae1362d9652b1ffb96b9acb2eaabe32a00426b43"
  depends_on "ai-vault"
  def install
    bin.install "ai-vault-http"
  end
  test do
    assert_predicate bin/"ai-vault-http", :exist?
  end
end
