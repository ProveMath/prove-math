package JSONRegex;

# regexs to recognize json values (BUT ONLY THE ONES I WILL BE USING):
our $frac = qr(\.\d+);
our $natural_number = qr(0|[1-9]\d*);
our $number = qr($natural_number$frac?);
our $slosh_follower = qr(["\\nt]|u[0-9a-f]{4});
our $illegal_slosh = qr(\\(?!$slosh_follower));
our $char = qr([^"\\]|\\$slosh_follower);
our $non_ntr_char = qr((?!\n|\t|\r)$char);
our $char_with_illegal_sloshes_allowed = qr([^"\\]|\\.);
our $string = qr("$char*");
our $string_with_illegal_sloshes_allowed = qr("$char_with_illegal_sloshes_allowed*");
our $base_value = qr($string|$number|true|false|null);

our $gobble_strings = qr((?:[^"]*$string)*[^"]*); # guarantees that what is immediately after this isn't in the middle of a string
our $gobble_mid_strings = qr($gobble_strings"$non_ntr_char*?);
our $nibble_strings = qr((?:[^"]*$string)*?[^"]*?); # reluctant version (first star greedy is ok)
our $nibble_strings_with_illegal_sloshes_allowed = qr((?:[^"]*$string_with_illegal_sloshes_allowed)*?[^"]*?);
our $gobble_strings_no_braces = qr((?:[^"{}]*$string)*[^"{}]*); # does not allow { or } outside of strings

our $line_containing_comment_with_illegal_sloshes_allowed = qr(^(?<PRECOMMENT>$nibble_strings_with_illegal_sloshes_allowed)//.*)m; # should be used with multi-line option
our $matched_braces = qr((?<MATCHEDBRACES>\{(?:$gobble_strings_no_braces(?&MATCHEDBRACES))*$gobble_strings_no_braces\}));
our $code_with_trailing_comma = qr/^(?<PRETRAILINGCOMMA>$gobble_strings(?:$base_value|\]|\})\s*),(?<POSTTRAILINGCOMMA>\s*[\]\}])/; # should be used with WHILE loop to get ALL trailing commas

1
