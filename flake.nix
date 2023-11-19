{
  outputs = {
    self,
    nixpkgs,
  }: let
    supportedSystems = ["x86_64-linux" "x86_64-darwin" "aarch64-linux" "aarch64-darwin"];
    forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    pkgs = forAllSystems (system: nixpkgs.legacyPackages.${system});
  in {
    packages = forAllSystems (system: {
      default = self.packages.${system}.openapi2jsonschema;

      openapi2jsonschema = pkgs.${system}.python3.pkgs.buildPythonApplication {
        pname = "openapi2jsonschema";
        version = self.dirtyShortRev or self.shortRev or "dirty";
        pyproject = true;

        src = ./.;

        propagatedBuildInputs = with pkgs.${system}.python3.pkgs; [
          pyyaml
          jsonref
          click
          kubernetes
        ];

        nativeBuildInputs = with pkgs.${system}.python3.pkgs; [
          setuptools
          pytestCheckHook
        ];

        nativeCheckInputs = with pkgs.${system}.python3.pkgs; [
          pytest-black
          pytest-isort
          pytest-cov
          pytest-datafiles
        ];

        dontUsePytestCheck = true;

        meta = with nixpkgs.lib; {
          description = "OpenAPI to JSON schemas converter";
          homepage = "https://github.com/stasjok/openapi2jsonschema";
          license = licenses.asl20;
          maintainers = with maintainers; [stasjok];
        };
      };
    });

    apps = forAllSystems (system: {
      default = self.apps.${system}.openapi2jsonschema;

      openapi2jsonschema = {
        type = "app";
        program = "${self.packages.${system}.openapi2jsonschema}/bin/openapi2jsonschema";
      };

      kube2jsonschema = {
        type = "app";
        program = "${self.packages.${system}.openapi2jsonschema}/bin/kube2jsonschema";
      };
    });

    devShells = forAllSystems (system: {
      default = pkgs.${system}.mkShellNoCC {
        name = "openapi2jsonschema";
        inputsFrom = [self.packages.${system}.default];
      };
    });

    checks = forAllSystems (system: {
      openapi2jsonschema = self.packages.${system}.openapi2jsonschema.overrideAttrs {
        dontUsePytestCheck = false;
      };
    });
  };
}
