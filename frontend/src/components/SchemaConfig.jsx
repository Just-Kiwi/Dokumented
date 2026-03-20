import React, { useState } from 'react'
import './SchemaConfig.css'

export const SchemaConfig = ({ onSchemaChange, onExtract, isLoading }) => {
  const [fields, setFields] = useState([
    { name: 'vendor_name', description: 'Name of the vendor/company', required: true },
    { name: 'invoice_date', description: 'Date of the invoice', required: true },
    { name: 'invoice_total', description: 'Total amount due', required: true },
    { name: 'invoice_number', description: 'Invoice reference number', required: true }
  ])

  const handleAddField = () => {
    setFields([
      ...fields,
      { name: '', description: '', required: true }
    ])
  }

  const handleRemoveField = (index) => {
    setFields(fields.filter((_, i) => i !== index))
  }

  const handleFieldChange = (index, key, value) => {
    const updated = [...fields]
    updated[index][key] = value
    setFields(updated)
    onSchemaChange(updated)
  }

  const handleExtract = () => {
    if (fields.length === 0) {
      alert('Please add at least one field to extract')
      return
    }

    if (fields.some(f => !f.name.trim())) {
      alert('All fields must have a name')
      return
    }

    onExtract(fields)
  }

  return (
    <div className="schema-config">
      <h2>Define Extraction Schema</h2>
      <p>Specify which fields you want to extract from the document:</p>

      <div className="fields-list">
        {fields.map((field, index) => (
          <div key={index} className="field-row">
            <input
              type="text"
              placeholder="Field name (e.g., vendor_name)"
              value={field.name}
              onChange={(e) => handleFieldChange(index, 'name', e.target.value)}
              className="field-input"
            />
            <input
              type="text"
              placeholder="Description (optional)"
              value={field.description}
              onChange={(e) => handleFieldChange(index, 'description', e.target.value)}
              className="field-input"
            />
            <label className="field-required">
              <input
                type="checkbox"
                checked={field.required}
                onChange={(e) => handleFieldChange(index, 'required', e.target.checked)}
              />
              Required
            </label>
            <button
              onClick={() => handleRemoveField(index)}
              className="remove-btn"
              disabled={isLoading}
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      <div className="schema-actions">
        <button
          onClick={handleAddField}
          className="add-field-btn"
          disabled={isLoading}
        >
          + Add Field
        </button>
        <button
          onClick={handleExtract}
          className="extract-btn"
          disabled={isLoading || fields.length === 0}
        >
          {isLoading ? 'Extracting...' : 'Start Extraction'}
        </button>
      </div>
    </div>
  )
}

export default SchemaConfig
