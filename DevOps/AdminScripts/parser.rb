#!/usr/bin/ruby

require 'erb'
require 'yaml'

class Parser
  
  attr_accessor :values

  def initialize(values)
    self.values = YAML::load(values)
  end

  def render(template)
    ERB.new(template).result(binding)
  end
  
  
  def method_missing(method_sym, *arguments, &block)
    if key_exists? method_sym.to_s
      return get_value method_sym.to_s
    else 
      raise "Template key not specified: #{method_sym}"
    end
  end

  def key_exists?(key)
    self.values['values'][key] != nil
  end

  def get_value(key)
    self.values['values'][key] 
  end
 
end

parser = Parser.new(File.read(ARGV[1]))
puts parser.render(File.read(ARGV[0]))