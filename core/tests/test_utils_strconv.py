"""
Tests for ayuna_core.utils.strconv module.

Tests the CaseConverter class and simple conversion functions for:
- kebab-case
- camelCase
- PascalCase
- snake_case
- COBOL-CASE
- MACRO_CASE
- flatlower
- FLATUPPER
"""

import pytest

from ayuna_core.basetypes import AyunaError
from ayuna_core.utils.strconv import (
    CaseConverter,
    lower_with_hyphens,
    lower_with_underscores,
)


class TestSimpleConversionFunctions:
    """Tests for the simple conversion functions."""

    def test_lower_with_underscores_basic(self):
        """Test basic underscore conversion."""
        assert lower_with_underscores("Hello World") == "hello_world"
        assert lower_with_underscores("hello-world") == "hello_world"
        assert lower_with_underscores("hello_world") == "hello_world"

    def test_lower_with_underscores_multiple_delimiters(self):
        """Test with multiple delimiters."""
        assert lower_with_underscores("Hello-World_Test") == "hello_world_test"
        assert lower_with_underscores("one two-three_four") == "one_two_three_four"

    def test_lower_with_hyphens_basic(self):
        """Test basic hyphen conversion."""
        assert lower_with_hyphens("Hello World") == "hello-world"
        assert lower_with_hyphens("hello_world") == "hello-world"
        assert lower_with_hyphens("hello-world") == "hello-world"

    def test_lower_with_hyphens_multiple_delimiters(self):
        """Test with multiple delimiters."""
        assert lower_with_hyphens("Hello-World_Test") == "hello-world-test"
        assert lower_with_hyphens("one two-three_four") == "one-two-three-four"


class TestCaseConverterKebabCase:
    """Tests for CaseConverter.to_kebabcase()."""

    def test_from_camel_case(self):
        """Test conversion from camelCase to kebab-case."""
        assert CaseConverter.to_kebabcase("helloWorld") == "hello-world"
        assert CaseConverter.to_kebabcase("myVariableName") == "my-variable-name"

    def test_from_pascal_case(self):
        """Test conversion from PascalCase to kebab-case."""
        assert CaseConverter.to_kebabcase("HelloWorld") == "hello-world"
        assert CaseConverter.to_kebabcase("MyClassName") == "my-class-name"

    def test_from_snake_case(self):
        """Test conversion from snake_case to kebab-case."""
        assert CaseConverter.to_kebabcase("hello_world") == "hello-world"
        assert CaseConverter.to_kebabcase("my_variable_name") == "my-variable-name"

    def test_from_space_separated(self):
        """Test conversion from space separated to kebab-case."""
        assert CaseConverter.to_kebabcase("hello world") == "hello-world"
        assert CaseConverter.to_kebabcase("My Variable Name") == "my-variable-name"

    def test_with_punctuation(self):
        """Test conversion with punctuation removal.

        Note: Punctuation is removed but doesn't create word boundaries,
        so 'hello.world' becomes 'helloworld' not 'hello-world'.
        """
        assert CaseConverter.to_kebabcase("hello.world!") == "helloworld"

    def test_empty_string_raises_error(self):
        """Test that empty string raises AyunaError."""
        with pytest.raises(AyunaError):
            CaseConverter.to_kebabcase("")


class TestCaseConverterCamelCase:
    """Tests for CaseConverter.to_camelcase()."""

    def test_from_kebab_case(self):
        """Test conversion from kebab-case to camelCase."""
        assert CaseConverter.to_camelcase("hello-world") == "helloWorld"
        assert CaseConverter.to_camelcase("my-variable-name") == "myVariableName"

    def test_from_snake_case(self):
        """Test conversion from snake_case to camelCase."""
        assert CaseConverter.to_camelcase("hello_world") == "helloWorld"
        assert CaseConverter.to_camelcase("my_variable_name") == "myVariableName"

    def test_from_space_separated(self):
        """Test conversion from space separated to camelCase."""
        assert CaseConverter.to_camelcase("hello world") == "helloWorld"
        assert CaseConverter.to_camelcase("My Variable Name") == "myVariableName"

    def test_from_pascal_case(self):
        """Test conversion from PascalCase to camelCase."""
        assert CaseConverter.to_camelcase("HelloWorld") == "helloWorld"

    def test_empty_string_raises_error(self):
        """Test that empty string raises AyunaError."""
        with pytest.raises(AyunaError):
            CaseConverter.to_camelcase("")


class TestCaseConverterPascalCase:
    """Tests for CaseConverter.to_pascalcase()."""

    def test_from_kebab_case(self):
        """Test conversion from kebab-case to PascalCase."""
        assert CaseConverter.to_pascalcase("hello-world") == "HelloWorld"
        assert CaseConverter.to_pascalcase("my-class-name") == "MyClassName"

    def test_from_snake_case(self):
        """Test conversion from snake_case to PascalCase."""
        assert CaseConverter.to_pascalcase("hello_world") == "HelloWorld"
        assert CaseConverter.to_pascalcase("my_class_name") == "MyClassName"

    def test_from_camel_case(self):
        """Test conversion from camelCase to PascalCase."""
        assert CaseConverter.to_pascalcase("helloWorld") == "HelloWorld"

    def test_from_space_separated(self):
        """Test conversion from space separated to PascalCase."""
        assert CaseConverter.to_pascalcase("hello world") == "HelloWorld"
        assert CaseConverter.to_pascalcase("my class name") == "MyClassName"

    def test_empty_string_raises_error(self):
        """Test that empty string raises AyunaError."""
        with pytest.raises(AyunaError):
            CaseConverter.to_pascalcase("")


class TestCaseConverterSnakeCase:
    """Tests for CaseConverter.to_snakecase()."""

    def test_from_camel_case(self):
        """Test conversion from camelCase to snake_case."""
        assert CaseConverter.to_snakecase("helloWorld") == "hello_world"
        assert CaseConverter.to_snakecase("myVariableName") == "my_variable_name"

    def test_from_pascal_case(self):
        """Test conversion from PascalCase to snake_case."""
        assert CaseConverter.to_snakecase("HelloWorld") == "hello_world"
        assert CaseConverter.to_snakecase("MyClassName") == "my_class_name"

    def test_from_kebab_case(self):
        """Test conversion from kebab-case to snake_case."""
        assert CaseConverter.to_snakecase("hello-world") == "hello_world"
        assert CaseConverter.to_snakecase("my-variable-name") == "my_variable_name"

    def test_from_space_separated(self):
        """Test conversion from space separated to snake_case."""
        assert CaseConverter.to_snakecase("hello world") == "hello_world"
        assert CaseConverter.to_snakecase("My Variable Name") == "my_variable_name"

    def test_empty_string_raises_error(self):
        """Test that empty string raises AyunaError."""
        with pytest.raises(AyunaError):
            CaseConverter.to_snakecase("")


class TestCaseConverterCobolCase:
    """Tests for CaseConverter.to_cobolcase()."""

    def test_from_camel_case(self):
        """Test conversion from camelCase to COBOL-CASE."""
        assert CaseConverter.to_cobolcase("helloWorld") == "HELLO-WORLD"
        assert CaseConverter.to_cobolcase("myVariableName") == "MY-VARIABLE-NAME"

    def test_from_snake_case(self):
        """Test conversion from snake_case to COBOL-CASE."""
        assert CaseConverter.to_cobolcase("hello_world") == "HELLO-WORLD"

    def test_from_kebab_case(self):
        """Test conversion from kebab-case to COBOL-CASE."""
        assert CaseConverter.to_cobolcase("hello-world") == "HELLO-WORLD"

    def test_already_uppercase(self):
        """Test that already uppercase strings are handled correctly."""
        result = CaseConverter.to_cobolcase("HELLO_WORLD")
        assert result == "HELLO-WORLD"

    def test_empty_string_raises_error(self):
        """Test that empty string raises AyunaError."""
        with pytest.raises(AyunaError):
            CaseConverter.to_cobolcase("")


class TestCaseConverterMacroCase:
    """Tests for CaseConverter.to_macrocase()."""

    def test_from_camel_case(self):
        """Test conversion from camelCase to MACRO_CASE."""
        assert CaseConverter.to_macrocase("helloWorld") == "HELLO_WORLD"
        assert CaseConverter.to_macrocase("myVariableName") == "MY_VARIABLE_NAME"

    def test_from_snake_case(self):
        """Test conversion from snake_case to MACRO_CASE."""
        assert CaseConverter.to_macrocase("hello_world") == "HELLO_WORLD"

    def test_from_kebab_case(self):
        """Test conversion from kebab-case to MACRO_CASE."""
        assert CaseConverter.to_macrocase("hello-world") == "HELLO_WORLD"

    def test_already_uppercase(self):
        """Test that already uppercase strings are handled correctly."""
        result = CaseConverter.to_macrocase("HELLO-WORLD")
        assert result == "HELLO_WORLD"

    def test_empty_string_raises_error(self):
        """Test that empty string raises AyunaError."""
        with pytest.raises(AyunaError):
            CaseConverter.to_macrocase("")


class TestCaseConverterFlatLower:
    """Tests for CaseConverter.to_flatlower()."""

    def test_from_camel_case(self):
        """Test conversion from camelCase to flatlower."""
        assert CaseConverter.to_flatlower("helloWorld") == "helloworld"
        assert CaseConverter.to_flatlower("myVariableName") == "myvariablename"

    def test_from_snake_case(self):
        """Test conversion from snake_case to flatlower."""
        assert CaseConverter.to_flatlower("hello_world") == "helloworld"

    def test_from_kebab_case(self):
        """Test conversion from kebab-case to flatlower."""
        assert CaseConverter.to_flatlower("hello-world") == "helloworld"

    def test_from_space_separated(self):
        """Test conversion from space separated to flatlower."""
        assert CaseConverter.to_flatlower("Hello World") == "helloworld"

    def test_empty_string_raises_error(self):
        """Test that empty string raises AyunaError."""
        with pytest.raises(AyunaError):
            CaseConverter.to_flatlower("")


class TestCaseConverterFlatUpper:
    """Tests for CaseConverter.to_flatupper()."""

    def test_from_camel_case(self):
        """Test conversion from camelCase to FLATUPPER."""
        assert CaseConverter.to_flatupper("helloWorld") == "HELLOWORLD"
        assert CaseConverter.to_flatupper("myVariableName") == "MYVARIABLENAME"

    def test_from_snake_case(self):
        """Test conversion from snake_case to FLATUPPER."""
        assert CaseConverter.to_flatupper("hello_world") == "HELLOWORLD"

    def test_from_kebab_case(self):
        """Test conversion from kebab-case to FLATUPPER."""
        assert CaseConverter.to_flatupper("hello-world") == "HELLOWORLD"

    def test_from_space_separated(self):
        """Test conversion from space separated to FLATUPPER."""
        assert CaseConverter.to_flatupper("Hello World") == "HELLOWORLD"

    def test_empty_string_raises_error(self):
        """Test that empty string raises AyunaError."""
        with pytest.raises(AyunaError):
            CaseConverter.to_flatupper("")


class TestCaseConverterOptions:
    """Tests for CaseConverter with custom options."""

    def test_custom_delimiters(self):
        """Test conversion with custom delimiters."""
        # Using pipe as delimiter
        result = CaseConverter.to_snakecase("hello|world", delimiters="|")
        assert result == "hello_world"

    def test_preserve_punctuation(self):
        """Test conversion with punctuation preservation."""
        # When clear_punctuation is False, non-delimiter punctuation is kept
        result = CaseConverter.to_snakecase("hello.world", clear_punctuation=False)
        assert "." in result

    def test_multiple_consecutive_delimiters(self):
        """Test handling of multiple consecutive delimiters."""
        result = CaseConverter.to_snakecase("hello---world")
        assert result == "hello_world"

    def test_leading_trailing_delimiters(self):
        """Test that leading/trailing delimiters are stripped."""
        result = CaseConverter.to_snakecase("---hello-world---")
        assert result == "hello_world"
