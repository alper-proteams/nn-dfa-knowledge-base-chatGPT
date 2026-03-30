import { useContext, useState, useEffect, useRef, useMemo, type FormEvent } from 'react'
import { FontIcon, Stack, TextField, Dropdown, IDropdownOption } from '@fluentui/react'
import { SendRegular } from '@fluentui/react-icons'

import Send from '../../assets/Send.svg'

import styles from './QuestionInput.module.css'
import { ChatMessage } from '../../api'
import { AppStateContext } from '../../state/AppProvider'
import { resizeImage } from '../../utils/resizeImage'

interface Props {
  onSend: (question: ChatMessage['content'], id?: string) => void
  disabled: boolean
  placeholder?: string
  clearOnSend?: boolean
  conversationId?: string
  initialQuestion?: string
  categoryOptions?: IDropdownOption[]
  selectedCategoryKeys?: string[]
  onCategoryChange?: (selectedKeys: string[]) => void
  categoryPlaceholder?: string
}

export const QuestionInput = ({
  onSend,
  disabled,
  placeholder,
  clearOnSend,
  conversationId,
  initialQuestion,
  categoryOptions,
  selectedCategoryKeys,
  onCategoryChange,
  categoryPlaceholder
}: Props) => {
  const [question, setQuestion] = useState<string>(initialQuestion || '')
  const [base64Image, setBase64Image] = useState<string | null>(null);
  const [autoSendTimer, setAutoSendTimer] = useState<number | null>(null);
  const questionSentRef = useRef(false);

  const sortedCategoryOptions = useMemo(() => {
    if (!categoryOptions?.length) {
      return []
    }

    return [...categoryOptions].sort((a, b) => {
      const aText = (a.text ?? '').toString()
      const bText = (b.text ?? '').toString()
      const aLower = aText.toLowerCase()
      const bLower = bText.toLowerCase()
      const aIsAll = aLower === 'all'
      const bIsAll = bLower === 'all'

      if (aIsAll && bIsAll) return 0
      if (aIsAll) return -1
      if (bIsAll) return 1

      return aLower.localeCompare(bLower)
    })
  }, [categoryOptions])

  const appStateContext = useContext(AppStateContext)
  const OYD_ENABLED = appStateContext?.state.frontendSettings?.oyd_enabled || false;
  
  // Implement typing effect for initial question
  useEffect(() => {
    if (initialQuestion && initialQuestion.trim() && !questionSentRef.current) {
      // Initialize with the first character and then add the rest one by one
      setQuestion(initialQuestion.charAt(0));
      let currentIndex = 1;
      const fullText = initialQuestion;
      
      // Function to add the next character
      const typeNextCharacter = () => {
        if (currentIndex < fullText.length) {
          // Create a complete string up to the current index
          const newValue = fullText.substring(0, currentIndex + 1);
          setQuestion(newValue);
          
          currentIndex++;
          // Continue typing with a slight delay between characters (100ms)
          setAutoSendTimer(setTimeout(typeNextCharacter, 100));
        } else {
          // Typing finished, wait a moment before sending
          setAutoSendTimer(setTimeout(() => {
            if (disabled) {
              return;
            }
            
            // Mark as sent to prevent infinite loops
            questionSentRef.current = true;
            
            const questionContent = fullText.toString();
            
            if (conversationId) {
              onSend(questionContent, conversationId);
            } else {
              onSend(questionContent);
            }
            
            if (clearOnSend) {
              setQuestion('');
            }
          }, 500)); // Short pause after typing completes before sending
        }
      };
      
      // Start the typing effect with a small initial delay
      setAutoSendTimer(setTimeout(() => {
        typeNextCharacter();
      }, 300));
      
      return () => {
        if (autoSendTimer) {
          clearTimeout(autoSendTimer);
        }
      };
    }
  }, [initialQuestion, disabled, conversationId, onSend, clearOnSend]); // Add all dependencies

  const handleImageUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];

    if (file) {
      await convertToBase64(file);
    }
  };

  const convertToBase64 = async (file: Blob) => {
    try {
      const resizedBase64 = await resizeImage(file, 800, 800);
      setBase64Image(resizedBase64);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  const sendQuestion = () => {
    if (disabled || !question.trim()) {
      return
    }

    const questionTest: ChatMessage["content"] = base64Image ? [{ type: "text", text: question }, { type: "image_url", image_url: { url: base64Image } }] : question.toString();

    if (conversationId && questionTest !== undefined) {
      onSend(questionTest, conversationId)
      setBase64Image(null)
    } else {
      onSend(questionTest)
      setBase64Image(null)
    }

    if (clearOnSend) {
      setQuestion('')
    }
  }

  const onEnterPress = (ev: React.KeyboardEvent<Element>) => {
    if (ev.key === 'Enter' && !ev.shiftKey && !(ev.nativeEvent?.isComposing === true)) {
      ev.preventDefault()
      sendQuestion()
    }
  }

  const onQuestionChange = (_ev: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>, newValue?: string) => {
    setQuestion(newValue || '')
  }

  const sendQuestionDisabled = disabled || !question.trim()

  const showCategoryDropdown = !!sortedCategoryOptions.length && !!onCategoryChange

  const isAllKey = (key?: string) => key?.toLowerCase() === 'all'

  const handleCategoryChange = (_ev: FormEvent<HTMLDivElement>, option?: IDropdownOption) => {
    if (!option) return

    const currentKeys = new Set(selectedCategoryKeys ?? [])
    const optionKey = option.key?.toString()

    if (optionKey && isAllKey(optionKey)) {
      onCategoryChange?.(option.selected ? [optionKey] : [])
      return
    }

    currentKeys.forEach(key => isAllKey(key) && currentKeys.delete(key))

    if (optionKey) {
      if (option.selected) {
        currentKeys.add(optionKey)
      } else {
        currentKeys.delete(optionKey)
      }
    }

    const nextKeys =
      currentKeys.size === 0
        ? [sortedCategoryOptions[0]?.key?.toString() ?? optionKey ?? 'all']
        : Array.from(currentKeys)
    onCategoryChange?.(nextKeys)
  }

  return (
    <Stack className={styles.questionInputWrapper}>
      <Stack horizontal className={styles.questionInputContainer}>
        <TextField
          className={styles.questionInputTextArea}
          placeholder={placeholder}
          multiline
          resizable={false}
          borderless
          value={question}
          onChange={onQuestionChange}
          onKeyDown={onEnterPress}
        />
        {!OYD_ENABLED && (
          <div className={styles.fileInputContainer}>
            <input
              type="file"
              id="fileInput"
              onChange={event => handleImageUpload(event)}
              accept="image/*"
              className={styles.fileInput}
            />
            <label htmlFor="fileInput" className={styles.fileLabel} aria-label="Upload Image">
              <FontIcon className={styles.fileIcon} iconName={'PhotoCollection'} aria-label="Upload Image" />
            </label>
          </div>
        )}
        {base64Image && <img className={styles.uploadedImage} src={base64Image} alt="Uploaded Preview" />}
        <div
          className={styles.questionInputSendButtonContainer}
          role="button"
          tabIndex={0}
          aria-label="Ask question button"
          onClick={sendQuestion}
          onKeyDown={e => (e.key === 'Enter' || e.key === ' ' ? sendQuestion() : null)}>
          {sendQuestionDisabled ? (
            <SendRegular className={styles.questionInputSendButtonDisabled} />
          ) : (
            <img src={Send} className={styles.questionInputSendButton} alt="Send Button" />
          )}
        </div>
        {showCategoryDropdown && (
          <div className={styles.categoryDropdownFloating}>
            <Dropdown
              ariaLabel="Select chat category"
              placeholder={categoryPlaceholder ?? 'Category'}
              multiSelect
              selectedKeys={selectedCategoryKeys ?? []}
              onChange={handleCategoryChange}
              options={sortedCategoryOptions}
              className={styles.categoryDropdownControl}
              styles={{
                dropdown: { minHeight: 36 }
              }}
            />
            <div className={styles.categoryDropdownBottomBorder} />
          </div>
        )}
        <div className={styles.questionInputBottomBorder} />
      </Stack>
    </Stack>
  )
}
